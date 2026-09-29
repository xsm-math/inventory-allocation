"""Seed-replicated experiments; run with python -m supplychain.benchmark."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import scipy
from scipy.stats import t as student_t
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .network import Network
from .simulation import run_episode

ROOT=Path(__file__).resolve().parents[1]
LABELS={'base_stock':'Base stock','mpc':'Rolling MILP','mpc_buffered':'Buffered MILP'}
COLORS={'base_stock':'#8795a5','mpc':'#236d91','mpc_buffered':'#258a75'}

def intervals(values):
    values=np.asarray(values,float);n=len(values)
    return float(values.mean()),float(student_t.ppf(.975,n-1)*values.std(ddof=1)/np.sqrt(n)) if n>1 else 0.

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seeds',type=int,default=12)
    parser.add_argument('--days',type=int,default=21)
    parser.add_argument('--time-limit',type=float,default=2.)
    args=parser.parse_args()
    if args.seeds<2 or args.days<7:parser.error('Use at least 2 seeds and 7 days')
    out=ROOT/'results/network';out.mkdir(exist_ok=True)
    n=Network.load();summaries=[];traces=[];channels=[];examples={}
    for regime in ['normal','surge','supply_shock']:
        for seed in range(101,101+args.seeds):
            for policy in LABELS:
                r=run_episode(n,seed,args.days,regime,policy,time_limit=args.time_limit,capture=seed==101)
                summaries.append(r['summary'])
                if seed==101:
                    traces+=r['daily'];channels += [dict(regime=regime,policy=policy,**c) for c in r['channels']]
                    examples[f'{regime}:{policy}']={k:v for k,v in r.items() if k!='decisions'}
            print(f'{regime} seed {seed} complete',flush=True)
    df=pd.DataFrame(summaries);df.to_csv(out/'episodes.csv',index=False)
    pd.DataFrame(traces).to_csv(out/'representative_daily.csv',index=False)
    pd.DataFrame(channels).to_csv(out/'representative_channels.csv',index=False)
    aggregate=[];comparisons=[]
    for (regime,policy),group in df.groupby(['regime','policy'],sort=False):
        value,ci=intervals(group.economic_value);fill,fill_ci=intervals(group.fill_rate)
        aggregate.append(dict(regime=regime,policy=policy,n=len(group),economic_value=value,value_ci95=ci,fill_rate=fill,fill_ci95=fill_ci,worst_channel_fill=group.worst_channel_fill.mean(),shipping=group.shipping.mean(),dispatch=group.dispatch.mean(),holding=group.holding.mean(),fallback_days=int(group.fallback_days.sum()),limit_days=int(group.limit_days.sum()),max_mip_gap=group.max_mip_gap.max(),mean_solve_seconds=group.mean_solve_seconds.mean()))
    for regime in df.regime.unique():
        group=df[df.regime==regime].pivot(index='seed',columns='policy',values='economic_value')
        for policy in ['mpc','mpc_buffered']:
            gain,ci=intervals(group[policy]-group.base_stock)
            comparisons.append(dict(regime=regime,policy=policy,mean_paired_gain=gain,ci95_halfwidth=ci,relative_gain=gain/group.base_stock.mean(),wins=int((group[policy]>group.base_stock).sum()),n=args.seeds))
    pd.DataFrame(aggregate).to_csv(out/'aggregate.csv',index=False)
    pd.DataFrame(comparisons).to_csv(out/'paired_comparisons.csv',index=False)
    # A short-horizon ablation uses the identical generator, constraints and economics.
    ablations=[]
    for regime in ['normal','supply_shock']:
        for seed in range(101,101+min(4,args.seeds)):
            for horizon in [3,7]:
                r=run_episode(n,seed,args.days,regime,'mpc',horizon=horizon,time_limit=args.time_limit)
                ablations.append(r['summary'])
    matched=df[(df.policy=='mpc') & df.regime.isin(['normal','supply_shock']) & (df.seed<105)]
    ablations+=matched.to_dict('records')
    pd.DataFrame(ablations).to_csv(out/'horizon_ablation.csv',index=False)
    metadata={'generated_at':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'config_sha256':hashlib.sha256((ROOT/'configs/network.json').read_bytes()).hexdigest(),'seeds':list(range(101,101+args.seeds)),'days':args.days,'horizon':5,'buffer_standard_deviations':.4,'time_limit_seconds':args.time_limit,'requested_mip_gap':.02,'synthetic_data':True}
    report={'metadata':metadata,'aggregate':aggregate,'paired_comparisons':comparisons,'examples':examples}
    (out/'report.json').write_text(json.dumps(report,separators=(',',':'),allow_nan=False))
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    plot(df,pd.DataFrame(aggregate),pd.DataFrame(traces),out)
    print(pd.DataFrame(aggregate).to_string(index=False))
    print(pd.DataFrame(comparisons).to_string(index=False))

def plot(df,ag,traces,out):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'inventory-network-study','svg.fonttype':'none'})
    fig,ax=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    regimes=['normal','surge','supply_shock'];xx=np.arange(3);width=.24
    for i,p in enumerate(LABELS):
        rows=ag[ag.policy==p].set_index('regime').loc[regimes]
        ax[0].bar(xx+(i-1)*width,rows.economic_value/1000,width,yerr=rows.value_ci95/1000,color=COLORS[p],label=LABELS[p],capsize=3)
        ax[1].bar(xx+(i-1)*width,rows.fill_rate*100,width,yerr=rows.fill_ci95*100,color=COLORS[p],capsize=3)
    for a in ax:a.set_xticks(xx,['Normal','Demand surge','Supply shock']);a.grid(axis='y',alpha=.15);a.set_axisbelow(True)
    ax[0].set_ylabel('Episode economic value / thousand CNY');ax[1].set_ylabel('Aggregate fill rate / %');ax[1].set_ylim(0,105)
    ax[0].legend(frameon=False,fontsize=9);fig.suptitle('Independent demand seeds; 95% t intervals across episodes')
    fig.savefig(out/'policy_comparison.svg');fig.savefig(out/'policy_comparison.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for j,regime in enumerate(regimes):
        for p in LABELS:
            g=traces[(traces.regime==regime)&(traces.policy==p)]
            axes[0,j].plot(g.day,g.sold.cumsum()/g.demand.cumsum()*100,color=COLORS[p],label=LABELS[p])
            axes[1,j].plot(g.day,g.warehouse_units+g.channel_units+g.pipeline_units,color=COLORS[p])
        axes[0,j].set_title(regime.replace('_',' ').title());axes[0,j].set_ylim(40,102)
        axes[1,j].set_xlabel('Day');axes[0,j].grid(alpha=.15);axes[1,j].grid(alpha=.15)
    axes[0,0].set_ylabel('Cumulative fill rate / %');axes[1,0].set_ylabel('On-hand + in-transit / units');axes[0,0].legend(frameon=False,fontsize=8)
    fig.suptitle('Representative trajectories: seed 101 (not an aggregate result)')
    fig.savefig(out/'trajectories.svg');plt.close(fig)

if __name__=='__main__':main()
