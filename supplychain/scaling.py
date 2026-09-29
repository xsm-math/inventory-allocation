"""Synthetic dimension study; repeated channels are not new empirical observations."""
import copy
from pathlib import Path
import pandas as pd
from .network import Network,State
from .forecast import predict,synthetic_history
from .planner import plan

def resized(warehouses,channels):
    base=Network.load().raw;d=copy.deepcopy(base)
    d['warehouses']=[f'W{i}' for i in range(warehouses)]
    d['channels']=[f'C{i}' for i in range(channels)]
    for key in ['price','shortage_penalty','mean_demand','channel_initial']:
        d[key]=[base[key][c%5] for c in range(channels)]
    for key in ['warehouse_initial','warehouse_handling']:
        d[key]=[base[key][w%3] for w in range(warehouses)]
    for key in ['ground_lead','ground_cost']:
        d[key]=[[base[key][w%3][c%5] for c in range(channels)] for w in range(warehouses)]
    d['supplier_capacity']=[round(x*channels/5) for x in base['supplier_capacity']]
    d['procurement_budget']*=channels/5
    return Network(d)

def main():
    rows=[]
    for w,c,h in [(2,4,3),(3,5,5),(5,10,7),(8,20,7)]:
        n=resized(w,c);history,_=synthetic_history(n,101)
        for repeat in range(3):
            try:
                a=plan(n,State.initial(n),predict(history,h),time_limit=3.)
                rows.append(dict(warehouses=w,channels=c,products=n.P,horizon=h,repeat=repeat,**a.diagnostics))
            except RuntimeError as exc:
                rows.append(dict(warehouses=w,channels=c,products=n.P,horizon=h,repeat=repeat,error=str(exc)))
    out=Path(__file__).resolve().parents[1]/'results/network/scaling.csv'
    pd.DataFrame(rows).to_csv(out,index=False)
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
