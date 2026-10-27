"""Post-freeze descriptive effects and figures; never selects a controller."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from supplychain.decision_study import load_frozen, option_array, paired_robust_difference
from supplychain.service_budget import write_csv,write_json,file_hash,paired_effects,plot_results
from supplychain.network import Network
from supplychain.forecast import synthetic_history


def required_budget_lower_bound(net,demands,regime,fill,worst):
    """Necessary common daily cap multiplier for empirical mean service.

    Ex-post pooled LP: future demand known, logistics and day-specific purchasing
    constraints relaxed; retain arriving supplier totals and a pooled cap per path.
    Average episode fill and episode worst-channel fill match the decision gates.
    """
    from scipy.optimize import linprog
    demands=np.asarray(demands,float)
    if (demands.ndim!=4 or demands.shape[2:]!=(net.C,net.P) or not np.isfinite(demands).all()
            or (demands<0).any() or not 0<=worst<=fill<=1 or regime not in {'normal','surge','supply_shock'}):
        raise ValueError('Invalid resource diagnostic inputs')
    n,days=demands.shape[:2]
    if n<1 or days<1 or (demands.sum((1,2,3))<=0).any():raise ValueError('Positive demand paths required')
    order_days=np.arange(max(0,days-net.supplier_lead))
    factors=np.where((order_days>=days//3)&(order_days<2*days//3),.45,1.) if regime=='supply_shock' else np.ones(len(order_days))
    supplier=np.floor(factors[:,None]*net.supplier_capacity).sum(0)
    pooled_budget=float(factors.sum()*net.procurement_budget)
    stock=net.warehouse_initial.sum(0)+net.channel_initial.sum(0)
    size=n*(net.C*net.P+net.P+1)+1;multiplier=size-1
    bounds=[];a=[];b=[];mean_fill=np.zeros(size);mean_worst=np.zeros(size)
    for i,demand in enumerate(demands):
        totals=demand.sum(0);offset=i*(net.C*net.P+net.P+1)
        sold=np.arange(offset,offset+net.C*net.P).reshape(net.C,net.P)
        purchase=np.arange(offset+net.C*net.P,offset+net.C*net.P+net.P)
        alpha=int(purchase[-1])+1
        bounds.extend([(0.,float(x)) for x in totals.ravel()]+[(0.,float(x)) for x in supplier]+[(0.,1.)])
        for product in range(net.P):
            row=np.zeros(size);row[sold[:,product]]=1;row[purchase[product]]=-1
            a.append(row);b.append(stock[product])
        row=np.zeros(size);row[purchase]=net.unit_cost;row[multiplier]=-pooled_budget
        a.append(row);b.append(0.)
        for channel in range(net.C):
            row=np.zeros(size);row[sold[channel]]=-1;row[alpha]=totals[channel].sum()
            a.append(row);b.append(0.)
        mean_fill[sold.ravel()]=-1/(n*totals.sum());mean_worst[alpha]=-1/n
    a.extend([mean_fill,mean_worst]);b.extend([-fill,-worst]);bounds.append((0.,None))
    cost=np.zeros(size);cost[multiplier]=1.
    r=linprog(cost,A_ub=np.asarray(a),b_ub=np.asarray(b),bounds=bounds,method='highs')
    if r.status==2:return None
    if not r.success:raise RuntimeError(r.message)
    return max(0.,float(r.fun))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    args=parser.parse_args();out=args.run_dir.resolve()
    p=json.loads((out/'selection.json').read_text(encoding='utf-8'))['protocol']
    frozen=load_frozen(p,out)
    v=json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if v['selection_sha256']!=file_hash(out/'selection.json') or any(file_hash(out/n)!=h for n,h in v['files'].items()):
        raise ValueError('Frozen evidence changed')
    df=pd.read_csv(out/'test_episodes.csv',float_precision='round_trip')
    write_csv(paired_effects(df,p),out/'paired_effects.csv')
    thresholds=pd.read_csv(out/'validation_fee_thresholds.csv')
    rows=[]
    for r in thresholds.to_dict('records'):
        if pd.isna(r['base_candidate']) or pd.isna(r['extra_candidate']):continue
        base={'candidate':r['base_candidate'],'resource':'base'}
        extra={'candidate':r['extra_candidate'],'resource':'budget_plus_10pct'}
        d,lo,hi=paired_robust_difference(option_array(df,extra,p,0),option_array(df,base,p,0),p['bootstrap_samples'])
        rows.append({**r,'heldout_gross_robust_budget_value_per_day':d/p['days'],
                     'heldout_budget_value_ci95_low':lo/p['days'],'heldout_budget_value_ci95_high':hi/p['days']})
    write_csv(pd.DataFrame(rows),out/'frozen_budget_value.csv')
    resource_rows=[];net=Network.load()
    for regime in p['regimes']:
        demands=np.array([synthetic_history(net,s,p['days'],regime)[1] for s in p['test_seeds']])
        for mandate in p['mandates']:
            lower=required_budget_lower_bound(net,demands,regime,mandate['fill'],mandate['worst'])
            resource_rows.append({'regime':regime,'mandate':mandate['name'],
                'minimum_relaxed_budget_multiplier':lower,
                'necessary_budget_increase_pct':100*max(0.,lower-1) if lower is not None else None,
                'relaxed_infeasible_even_with_unlimited_budget':lower is None})
    write_csv(pd.DataFrame(resource_rows),out/'necessary_budget_lower_bound.csv')
    summary=pd.read_csv(out/'test_summary.csv');summary['family']=summary.candidate
    broad=next(x for x in p['mandates'] if x['name']=='broad_service')
    plot_results(summary,out,{**p,'selection_target':broad})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'svg.fonttype':'none','svg.hashsalt':'decision-study-v1'})
    eligible=pd.read_csv(out/'validation_eligibility.csv')
    colors={'stock':'#64748b','economic_milp':'#0369a1','service_milp':'#b45309'}
    fig,axes=plt.subplots(2,2,figsize=(13,8),sharex=True,layout='constrained')
    fees=np.linspace(0,max(p['fees_per_day']),101)
    for ax,mandate in zip(axes.ravel(),p['mandates']):
        g=eligible[(eligible.mandate==mandate['name']) & eligible.eligible]
        for r in g.to_dict('records'):
            expanded=r['resource']!='base'
            value=(r['worst_regime_value']-expanded*p['days']*fees)/1000
            ax.plot(fees,value,color=colors[r['candidate']],linestyle='--' if expanded else '-')
        for d in frozen['decisions']:
            if d['mandate']==mandate['name'] and d['selected']:
                s=d['selected'];ax.scatter(d['fee_per_day'],s['net_worst_regime_value']/1000,
                    color=colors[s['candidate']],edgecolor='black',s=45,zorder=4)
        if g.empty:ax.text(.5,.5,'No eligible option',ha='center',transform=ax.transAxes)
        ax.set_title(f"{mandate['name']} (fill >= {mandate['fill']:.0%}, worst >= {mandate['worst']:.0%})")
        ax.set_xlabel('Extra-budget facility fee / illustrative CNY per day')
        ax.set_ylabel('Minimum-regime net value / thousand CNY');ax.grid(alpha=.2)
    handles=[Line2D([0],[0],color=c,label=k) for k,c in colors.items()]
    handles += [Line2D([0],[0],color='black',linestyle=s,label=k) for s,k in [('-','base'),('--','budget +10%')]]
    axes[0,0].legend(handles=handles,fontsize=8)
    fig.suptitle('Validation decisions frozen before held-out paths; dots mark declared fee choices')
    fig.savefig(out/'decision_rule.png',dpi=160);fig.savefig(out/'decision_rule.svg');plt.close(fig)
    write_json(out/'diagnostics_manifest.json',{'diagnostic_only':True,
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'selection_sha256':file_hash(out/'selection.json'),'test_files':v['files'],
        'files':{n:file_hash(out/n) for n in ['paired_effects.csv','frozen_budget_value.csv','necessary_budget_lower_bound.csv','service.png','service.svg',
             'economics.png','economics.svg','decision_rule.png','decision_rule.svg']}})
    # Report-only clarification: no storage-volume cap exists in the physical
    # model. Preserve every frozen input and refresh hashes of derived artifacts.
    report=out/'REPORT.md'
    report_text=report.read_text(encoding='utf-8').replace('timing/lane/storage restrictions',
        'timing/lane/warehouse-handling restrictions')
    clarification='The physical model has no storage-volume cap. Figures and paired descriptive effects are generated by scripts/decision_diagnostics.py; they do not alter frozen decisions.'
    if clarification not in report_text:report_text+='\n'+clarification+'\n'
    report.write_text(report_text,encoding='utf-8',newline='\n')
    manifest=json.loads((out/'run_manifest.json').read_text(encoding='utf-8'))
    manifest['files']={x.name:file_hash(x) for x in sorted(out.iterdir()) if x.is_file() and x.name!='run_manifest.json'}
    manifest['report_postprocessor_sha256']=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    write_json(out/'run_manifest.json',manifest)
    print('Descriptive effects and validation decision figures saved; frozen choices unchanged.')


if __name__=='__main__':main()
