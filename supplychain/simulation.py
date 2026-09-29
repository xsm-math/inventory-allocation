"""Order-before-demand simulation with physical conservation and cost ledgers."""
import hashlib
import numpy as np
from .network import State, validate_action
from .forecast import synthetic_history, predict
from .policies import decide


def execute(net,state,action,day,demand,supply_factor=1.):
    validate_action(net,state,action,supply_factor)
    demand=np.asarray(demand)
    if demand.shape!=(net.C,net.P) or not np.isfinite(demand).all() or (demand<0).any() or (demand%1).any():
        raise ValueError('Invalid realized demand')
    before=state.total_by_product()
    state.warehouse-=action.shipments.sum((1,2))
    for w in range(net.W):
        for c in range(net.C):
            for mode in range(2):
                units=action.shipments[w,c,mode]
                lead=int(net.lead[w,c,mode])
                if lead==0:state.channel[c]+=units
                else:
                    arrival=day+lead
                    if arrival not in state.outbound:state.outbound[arrival]=np.zeros_like(state.channel)
                    state.outbound[arrival][c]+=units
    arrival=day+net.supplier_lead
    if action.orders.sum():
        if arrival not in state.inbound:state.inbound[arrival]=np.zeros_like(state.warehouse)
        state.inbound[arrival]+=action.orders
    sold=np.minimum(state.channel,demand);lost=demand-sold
    state.channel-=sold
    after=state.total_by_product()
    mass_error=after-(before+action.orders.sum(0)-sold.sum(0))
    if np.any(mass_error) or (state.warehouse<0).any() or (state.channel<0).any():
        raise AssertionError('Physical inventory conservation failed')
    shipping=float((action.shipments*net.volume*net.freight[:,:,:,None]).sum())
    dispatch=float(((action.shipments.sum(-1)>0)*net.dispatch_fixed_cost).sum())
    record={'day':day,'demand':int(demand.sum()),'sold':int(sold.sum()),'lost':int(lost.sum()),
            'revenue':float((sold*net.price).sum()),'procurement':float((action.orders*net.unit_cost).sum()),
            'shipping':shipping,'dispatch':dispatch,
            'holding':float((state.warehouse*net.warehouse_holding).sum()+(state.channel*net.channel_holding).sum()),
            'shortage_penalty':float((lost*net.shortage_penalty).sum()),
            'warehouse_units':int(state.warehouse.sum()),'channel_units':int(state.channel.sum()),
            'pipeline_units':int(after.sum()-state.warehouse.sum()-state.channel.sum()),
            'orders':int(action.orders.sum()),'ground_units':int(action.shipments[:,:,0,:].sum()),'express_units':int(action.shipments[:,:,1,:].sum()),
            'active_dispatches':int((action.shipments.sum(-1)>0).sum()),'mass_balance_error':int(abs(mass_error).max()),**action.diagnostics}
    record['operating_value']=record['revenue']-sum(record[k] for k in ['procurement','shipping','dispatch','holding','shortage_penalty'])
    return record,sold,lost


def run_episode(net,seed=101,days=20,regime='normal',policy='mpc',horizon=5,time_limit=2.,capture=False):
    if days<1 or horizon<1:raise ValueError('Positive days and horizon required')
    training,actual=synthetic_history(net,seed,days,regime)
    state=State.initial(net);history=training.copy()
    records=[];decisions=[];channel_sold=np.zeros((net.C,net.P),int);channel_demand=channel_sold.copy()
    errors=[]
    initial_value=float(state.total_by_product()@net.unit_cost)
    for day in range(days):
        state.receive(day)
        # Only the current supply restriction is observed; its future duration is unknown.
        factor=.45 if regime=='supply_shock' and days//3<=day<2*days//3 else 1.
        forecast=predict(history,1)[0]
        action=decide(net,state,history,day,days-day,policy,horizon,factor,time_limit)
        record,sold,lost=execute(net,state,action,day,actual[day],factor)
        record.update(seed=seed,regime=regime,policy=policy,supply_factor=factor)
        records.append(record);channel_sold+=sold;channel_demand+=actual[day]
        errors.append(abs(forecast-actual[day]).sum())
        if capture:
            decisions.append({'day':day,'orders':action.orders.tolist(),'shipments':action.shipments.tolist(),'forecast':forecast.tolist(),'actual':actual[day].tolist(),'warehouse_end':state.warehouse.tolist(),'channel_end':state.channel.tolist()})
        history=np.concatenate([history,actual[day:day+1]])
    salvage=float(net.salvage_fraction*(state.total_by_product()@net.unit_cost))
    sold_total=sum(r['sold'] for r in records);demand_total=int(actual.sum())
    gaps=[r['mip_gap'] for r in records if r.get('mip_gap') is not None]
    summary={'seed':seed,'regime':regime,'policy':policy,'days':days,'horizon':horizon,
             'economic_value':sum(r['operating_value'] for r in records)-initial_value+salvage,
             'fill_rate':sold_total/demand_total if demand_total else 1.,
             'worst_channel_fill':float(np.min(np.divide(channel_sold.sum(1),channel_demand.sum(1),out=np.ones(net.C),where=channel_demand.sum(1)>0))),
             'demand':demand_total,'sold':sold_total,'terminal_units':int(state.total_by_product().sum()),
             'terminal_salvage':salvage,'initial_inventory_charge':initial_value,
             'forecast_wape':sum(errors)/demand_total if demand_total else 0.,
             'fallback_days':sum(r['fallback'] for r in records),
             'limit_days':sum(r['solver_status']==1 for r in records),
             'max_mip_gap':max(gaps,default=0.),'mean_solve_seconds':float(np.mean([r['solve_seconds'] for r in records])),
             'max_variables':max(r['variables'] for r in records),'max_constraints':max(r['constraints'] for r in records),
             'demand_sha256':hashlib.sha256(actual.tobytes()).hexdigest()}
    for k in ['revenue','procurement','shipping','dispatch','holding','shortage_penalty','express_units','ground_units','active_dispatches']:
        summary[k]=sum(r[k] for r in records)
    channels=[{'channel':net.raw['channels'][c],'sold':int(channel_sold[c].sum()),'demand':int(channel_demand[c].sum()),'fill_rate':float(channel_sold[c].sum()/max(channel_demand[c].sum(),1))} for c in range(net.C)]
    return {'summary':summary,'daily':records,'channels':channels,'decisions':decisions}
