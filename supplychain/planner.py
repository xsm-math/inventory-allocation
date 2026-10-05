"""Sparse mixed-integer receding-horizon inventory/transport model."""
from time import perf_counter
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from .network import Action, validate_action

class Model:
    def __init__(self):
        self.c=[];self.ub=[];self.integer=[];self.row=[];self.col=[];self.val=[];self.lo=[];self.hi=[]
    def vars(self,shape,cost=0,upper=np.inf,integer=False):
        n=int(np.prod(shape));v=np.arange(len(self.c),len(self.c)+n).reshape(shape)
        self.c.extend(np.broadcast_to(cost,shape).ravel());self.ub.extend(np.broadcast_to(upper,shape).ravel());self.integer.extend([int(integer)]*n)
        return v
    def constraint(self, terms, lower=-np.inf, upper=np.inf):
        r=len(self.lo)
        for indices,coeff in terms:
            idx=np.asarray(indices).ravel();coef=np.broadcast_to(coeff,np.asarray(indices).shape).ravel()
            self.row.extend([r]*len(idx));self.col.extend(idx);self.val.extend(coef)
        self.lo.append(lower);self.hi.append(upper)
    def solve(self,time_limit,gap):
        A=coo_matrix((self.val,(self.row,self.col)),shape=(len(self.lo),len(self.c))).tocsc()
        result=milp(np.asarray(self.c),integrality=np.asarray(self.integer),bounds=Bounds(np.zeros(len(self.c)),self.ub),constraints=LinearConstraint(A,self.lo,self.hi),options={'time_limit':time_limit,'mip_rel_gap':gap})
        return result,A


def plan(net,state,forecast,day=0,supply_factor=1.,time_limit=2.,gap=.02, service=True, safety=None):
    d=np.asarray(forecast,float)
    if d.ndim!=3 or d.shape[1:]!=(net.C,net.P) or len(d)<1 or not np.isfinite(d).all() or (d<0).any() or (d%1).any():
        raise ValueError('Forecast must be integer horizon/channel/product demand')
    if not np.isfinite(supply_factor) or not 0<=supply_factor<=1 or time_limit<=0 or not 0<=gap<=1:
        raise ValueError('Invalid solver or supply settings')
    H=len(d);m=Model();start=perf_counter()
    # Integer physical controls; linear inventory and sales variables remain continuous.
    q_upper=np.broadcast_to(np.floor(net.supplier_capacity*supply_factor),(H,net.W,net.P)).copy()
    q_upper[max(0,H-net.supplier_lead):]=0
    q=m.vars((H,net.W,net.P),net.unit_cost,q_upper,True)
    xupper=np.empty((H,net.W,net.C,2,net.P))
    for t in range(H):
        xupper[t]=net.lane_capacity[None,None,:,None]/net.volume[None,None,None,:]
        for w in range(net.W):
            for c in range(net.C):
                for mode in range(2):
                    if t+net.lead[w,c,mode]>=H:xupper[t,w,c,mode]=0
    freight=net.freight[:,:,:,None]*net.volume
    x=m.vars(xupper.shape,freight,xupper,True)
    z=m.vars((H,net.W,net.C,2),net.dispatch_fixed_cost,1,True)
    iwcost=np.broadcast_to(net.warehouse_holding,(H,net.W,net.P)).copy()
    iccost=np.broadcast_to(net.channel_holding,(H,net.C,net.P)).copy()
    iwcost[-1]-=net.salvage_fraction*net.unit_cost
    iccost[-1]-=net.salvage_fraction*net.unit_cost
    iw=m.vars((H,net.W,net.P),iwcost)
    ic=m.vars((H,net.C,net.P),iccost)
    if safety is not None:
        safety=np.asarray(safety,float)
        if safety.shape != (net.C,net.P) or not np.isfinite(safety).all() or (safety<0).any():
            raise ValueError('Invalid safety-stock target')
        buffer_slack=m.vars((H,net.C,net.P),net.raw.get('safety_slack_penalty',8.))
        # Release the reserve as the finite episode/horizon approaches its end.
        for t in range(H):
            taper=min(1.,(H-1-t)/net.supplier_lead)
            for c in range(net.C):
                for p in range(net.P):
                    m.constraint([(ic[t,c,p],1),(buffer_slack[t,c,p],1)],lower=taper*safety[c,p])
    sold=m.vars(d.shape,-net.price,d)
    lost=m.vars(d.shape,net.shortage_penalty,d)
    slack=m.vars((net.C,net.P),net.service_slack_penalty if service else 0)
    for t in range(H):
        for p in range(net.P):
            m.constraint([(q[t,:,p],1)],upper=np.floor(net.supplier_capacity[p]*supply_factor))
        m.constraint([(q[t],net.unit_cost)],upper=net.procurement_budget*supply_factor)
        for w in range(net.W):
            m.constraint([(x[t,w],net.volume)],upper=net.warehouse_handling[w])
            for c in range(net.C):
                for mode in range(2):
                    m.constraint([(x[t,w,c,mode],net.volume),(z[t,w,c,mode],-net.lane_capacity[mode])],upper=0)
            for p in range(net.P):
                terms=[(iw[t,w,p],1),(x[t,w,:,:,p],1)]
                rhs=state.warehouse[w,p] if t==0 else 0
                if t:terms.append((iw[t-1,w,p],-1))
                rhs+=state.inbound.get(day+t,np.zeros_like(state.warehouse))[w,p]
                if t>=net.supplier_lead:terms.append((q[t-net.supplier_lead,w,p],-1))
                m.constraint(terms,rhs,rhs)
        for c in range(net.C):
            for p in range(net.P):
                terms=[(ic[t,c,p],1),(sold[t,c,p],1)]
                rhs=state.channel[c,p] if t==0 else 0
                if t:terms.append((ic[t-1,c,p],-1))
                rhs+=state.outbound.get(day+t,np.zeros_like(state.channel))[c,p]
                for w in range(net.W):
                    for mode in range(2):
                        departure=t-net.lead[w,c,mode]
                        if departure>=0:terms.append((x[departure,w,c,mode,p],-1))
                m.constraint(terms,rhs,rhs)
                m.constraint([(sold[t,c,p],1),(lost[t,c,p],1)],d[t,c,p],d[t,c,p])
    for c in range(net.C):
        for p in range(net.P):
            m.constraint([(sold[:,c,p],1),(slack[c,p],1)],lower=(net.service_target if service else 0)*d[:,c,p].sum())
    res,A=m.solve(time_limit,gap)
    diag={'solver_status':int(res.status),'solver_message':res.message,'solve_seconds':perf_counter()-start,'variables':len(m.c),'constraints':len(m.lo),'integer_variables':sum(m.integer),'mip_gap':None,'fallback':False}
    if res.x is None:
        raise RuntimeError(f'No feasible incumbent: {res.message}')
    v=res.x
    if not np.isfinite(v).all() or not np.isfinite(res.fun):
        raise RuntimeError('Nonfinite solver incumbent')
    violation=max(float(np.maximum(np.asarray(m.lo)-A@v,0).max()),float(np.maximum(A@v-np.asarray(m.hi),0).max()),float(np.maximum(-v,0).max()),float(np.maximum(v-np.asarray(m.ub),0).max()))
    integer_error=float(np.abs(v[np.asarray(m.integer,dtype=bool)]-np.rint(v[np.asarray(m.integer,dtype=bool)])).max())
    if violation>1e-5 or integer_error>1e-5:
        raise RuntimeError('Solver incumbent failed feasibility checks')
    diag.update(mip_gap=float(getattr(res,'mip_gap',0)),planning_objective=float(res.fun),max_constraint_violation=violation)
    action=Action(np.rint(v[q[0]]).astype(int),np.rint(v[x[0]]).astype(int),diag)
    validate_action(net,state,action,supply_factor)
    return action
