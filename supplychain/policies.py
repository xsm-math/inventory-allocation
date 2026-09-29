"""Base-stock benchmark and optimization policies sharing the same observations."""
import numpy as np
from .network import Action, validate_action
from .forecast import predict
from .planner import plan

POLICIES=('base_stock','mpc','mpc_buffered')

def base_stock(net,state,forecast,day,supply_factor=1.):
    action=Action.zero(net)
    H=len(forecast);mean=forecast.mean(0)
    future=sum(state.outbound.values(),np.zeros_like(state.channel))
    position=state.channel.astype(float)+future
    availability=state.warehouse.copy();handling=net.warehouse_handling.copy()
    lane=net.lane_capacity[None,None,:]*np.ones((net.W,net.C,2),int)
    # Cover immediate shortfalls with express; replenish future needs by ground.
    for mode in [1,0]:
        priorities=sorted(((c,p) for c in range(net.C) for p in range(net.P)),key=lambda cp:position[cp]/max(mean[cp],1))
        for c,p in priorities:
            for w in np.argsort(net.freight[:,c,mode]):
                lead=int(net.lead[w,c,mode])
                if lead>=H:continue
                target=forecast[:min(H,lead+2)].sum(0)[c,p] if mode==0 else forecast[0,c,p]
                # Express must cover only today's on-hand shortfall, excluding future arrivals.
                already=action.shipments[:,c,1,p].sum()
                needed=max(0,target-(state.channel[c,p]+already if mode==1 else position[c,p]))
                count=int(min(needed,availability[w,p],handling[w]//net.volume[p],lane[w,c,mode]//net.volume[p]))
                action.shipments[w,c,mode,p]+=count
                availability[w,p]-=count;handling[w]-=count*net.volume[p];lane[w,c,mode]-=count*net.volume[p]
                position[c,p]+=count
    # Network base stock; orders are apportioned by geographical demand affinity.
    if H>net.supplier_lead:
        coverage=min(H,net.supplier_lead+int(net.ground_lead.max())+2)
        target=forecast[:coverage].sum((0,1))
        desired=np.minimum(np.maximum(0,target-state.total_by_product()),np.floor(net.supplier_capacity*supply_factor)).astype(int)
        budget=net.procurement_budget*supply_factor
        if desired@net.unit_cost>budget:
            desired=np.floor(desired*budget/(desired@net.unit_cost)).astype(int)
        weights=np.zeros((net.W,net.P))
        for c in range(net.C):
            w=int(np.argmin(net.ground_cost[:,c]))
            weights[w]+=mean[c]
        for p in range(net.P):
            shares=weights[:,p]/max(weights[:,p].sum(),1)
            if shares.sum()==0:shares=np.ones(net.W)/net.W
            raw=desired[p]*shares;counts=np.floor(raw).astype(int)
            for w in np.argsort(-(raw-counts))[:desired[p]-counts.sum()]:counts[w]+=1
            action.orders[:,p]=counts
    action.diagnostics={'solver_status':-1,'solve_seconds':0.,'mip_gap':None,'fallback':False,'variables':0,'constraints':0,'integer_variables':0}
    validate_action(net,state,action,supply_factor)
    return action


def decide(net,state,history,day,remaining,policy,horizon=5,supply_factor=1.,time_limit=2.):
    if policy not in POLICIES:raise ValueError('Unknown policy')
    H=min(remaining,max(horizon,net.supplier_lead+int(net.ground_lead.max())+2)) if policy=='base_stock' else min(remaining,horizon)
    demand=predict(history,H,buffer=.4 if policy=='mpc_buffered' else 0.)
    if policy=='base_stock':return base_stock(net,state,demand,day,supply_factor)
    try:
        return plan(net,state,demand,day,supply_factor,time_limit)
    except RuntimeError as exc:
        action=base_stock(net,state,demand,day,supply_factor)
        action.diagnostics.update(fallback=True,solver_status=4,solver_message=str(exc))
        return action
