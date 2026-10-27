"""Frozen service-priority policy and a paired policy-by-budget experiment."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.metadata
import itertools
import json
import platform

import numpy as np
import pandas as pd

from .network import Network
from .simulation import run_episode
from .forecast import synthetic_history
from .frontier import ROOT, digest, source_hashes, interval, check_episodes
from scripts.capacity_bound import service_bound

METRICS=('economic_value','fill_rate','worst_channel_fill','procurement')


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def write_csv(df,path):
    df.to_csv(path,index=False,lineterminator='\n',float_format='%.17g')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(p):
    return {'protocol':digest(p),'sources':source_hashes(),'network':digest(Network.load().raw),
            'prior_protocol':file_hash(ROOT/'configs/service_frontier.json'),
            'bound_script':hashlib.sha256((ROOT/'scripts/capacity_bound.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()}


def validate_protocol(p):
    partitions=['development_seeds','runtime_development_seeds','validation_seeds','test_seeds']
    for key in partitions:
        s=p[key]
        if not s or any(type(x) is not int or x<0 for x in s) or len(s)!=len(set(s)):
            raise ValueError('Invalid seed partition')
    for a,b in itertools.combinations(partitions,2):
        if set(p[a]) & set(p[b]):raise ValueError('Overlapping seed partitions')
    prior=json.loads((ROOT/'configs/service_frontier.json').read_text(encoding='utf-8'))
    known=set(prior['development_seeds']+prior['validation_seeds']+prior['test_seeds'])
    if known & set(p['validation_seeds']+p['test_seeds']):
        raise ValueError('New partitions reuse previously inspected paths')
    if min(len(p['validation_seeds']),len(p['test_seeds']))<2:
        raise ValueError('At least two validation and test paths required')
    if type(p['days']) is not int or p['days']<7 or type(p['horizon']) is not int or p['horizon']<1:
        raise ValueError('Invalid operating/planning horizon')
    if not p['regimes'] or len(set(p['regimes']))!=len(p['regimes']) or set(p['regimes'])-{'normal','surge','supply_shock'}:
        raise ValueError('Invalid regimes')
    if (isinstance(p['time_limit'],bool) or not np.isfinite(p['time_limit']) or p['time_limit']<=0
            or type(p['stock_review_days']) is not int or p['stock_review_days']<1):
        raise ValueError('Invalid solver/review setting')
    for key,low,high in [('forecast_buffer',0,2),('service_goal',0,1),('service_precision',0,1),('planning_service_penalty',0,np.inf)]:
        x=p[key]
        if isinstance(x,bool) or not np.isfinite(x) or not low<=x<=high:raise ValueError('Invalid planning control')
    ts=p['service_tolerances']
    if not ts or len(set(ts))!=len(ts) or any(isinstance(x,bool) or not np.isfinite(x) or not 0<=x<=1 for x in ts):
        raise ValueError('Invalid service tolerances')
    if [r['name'] for r in p['resources']]!=['base','budget_plus_10pct'] or [r['budget_multiplier'] for r in p['resources']]!=[1.,1.1]:
        raise ValueError('This declared factorial design is base versus budget +10%')
    profiles=[p['selection_target'],*p['report_profiles']]
    if not p['report_profiles'] or len({x['name'] for x in p['report_profiles']})!=len(p['report_profiles']):
        raise ValueError('Invalid report profiles')
    for x in profiles:
        if not np.isfinite([x['fill'],x['worst']]).all() or not 0<=x['worst']<=x['fill']<=1:
            raise ValueError('Invalid service target')
    return p


def candidates(p):
    controls=[{'id':'stock','family':'stock','policy':'base_stock',
               'options':{'review_days':p['stock_review_days'],'forecast_buffer':0.},'network_overrides':{}},
              {'id':'economic_milp','family':'economic_milp','policy':'mpc',
               'options':{'forecast_buffer':p['forecast_buffer']},
               'network_overrides':{'service_slack_penalty':p['planning_service_penalty']}}]
    return controls+[{'id':f'service-d{t:g}','family':'service_milp','policy':'mpc_service',
                      'options':{'forecast_buffer':p['forecast_buffer'],'service_goal':p['service_goal'],
                                 'service_tolerance':t,'service_precision':p['service_precision']},
                      'network_overrides':{'service_slack_penalty':p['planning_service_penalty']}}
                     for t in p['service_tolerances']]


def network_for(resource,spec):
    raw=copy.deepcopy(Network.load().raw)
    raw['procurement_budget']*=resource['budget_multiplier']
    raw.update(spec['network_overrides'])
    return Network(raw)


def check_grid(df,p,specs,seeds):
    if set(df.resource)!=set(x['name'] for x in p['resources']):raise ValueError('Missing resource condition')
    error=0.
    for resource in p['resources']:
        error=max(error,check_episodes(df[df.resource==resource['name']],specs,seeds,p['regimes']))
    if (df.groupby(['regime','seed']).demand_sha256.nunique()!=1).any():
        raise ValueError('Budget changes altered paired demand paths')
    return error


def run_grid(p,specs,seeds,out,stage):
    rows=[];channels=[];daily=[]
    for resource in p['resources']:
        nets={s['id']:network_for(resource,s) for s in specs}
        for regime in p['regimes']:
            for seed in seeds:
                for spec in specs:
                    r=run_episode(nets[spec['id']],seed=seed,days=p['days'],regime=regime,
                                  policy=spec['policy'],horizon=p['horizon'],time_limit=p['time_limit'],
                                  policy_options=spec['options'])
                    identity={'resource':resource['name'],'candidate':spec['id'],'family':spec['family'],
                              'seed':seed,'regime':regime}
                    rows.append({**identity,**r['summary']})
                    if stage=='test':
                        channels.extend([{**identity,**x} for x in r['channels']])
                        if seed==seeds[0]:daily.extend([{**identity,**x} for x in r['daily']])
                write_csv(pd.DataFrame(rows),out/f'{stage}_progress.csv')
                print(f'{stage}: {resource["name"]}/{regime} seed {seed}; {len(rows)} episodes',flush=True)
    df=pd.DataFrame(rows)
    error=check_grid(df,p,specs,seeds)
    write_csv(df,out/f'{stage}_episodes.csv')
    (out/f'{stage}_progress.csv').unlink()
    if stage=='test':
        write_csv(pd.DataFrame(channels),out/'test_channels.csv')
        write_csv(pd.DataFrame(daily),out/'representative_daily.csv')
    return df,error


def validation_statistics(df):
    cells=df.groupby(['candidate','family','resource','regime'],as_index=False).agg(
        value=('economic_value','mean'),fill=('fill_rate','mean'),worst=('worst_channel_fill','mean'))
    stats=cells.groupby(['candidate','family'],as_index=False).agg(
        mean_value=('value','mean'),min_fill=('fill','min'),min_worst=('worst','min'))
    return cells,stats


def select_service(stats,target):
    s=stats[stats.family=='service_milp'].copy()
    if s.empty:raise ValueError('No service-priority candidates')
    s['deficit']=np.maximum(np.maximum(target['fill']-s.min_fill,0),np.maximum(target['worst']-s.min_worst,0))
    eligible=s[s.deficit<=1e-12]
    selected=(eligible.sort_values(['mean_value','candidate'],ascending=[False,True]).iloc[0] if len(eligible)
              else s.sort_values(['deficit','mean_value','candidate'],ascending=[True,False,True]).iloc[0])
    return {'candidate':selected.candidate,'validation_eligible':bool(len(eligible)),
            'validation_min_fill':float(selected.min_fill),'validation_min_worst':float(selected.min_worst),
            'validation_max_deficit':float(selected.deficit),'validation_mean_value':float(selected.mean_value)}


def validate_stage(p,out):
    if (out/'selection.json').exists() or (out/'test_episodes.csv').exists():
        raise FileExistsError('Choose a fresh output directory')
    signature=fingerprint(p)
    specs=candidates(p)
    df,error=run_grid(p,specs,p['validation_seeds'],out,'validation')
    if signature!=fingerprint(p):raise ValueError('Inputs changed during validation')
    cells,stats=validation_statistics(df)
    write_csv(cells,out/'validation_cells.csv');write_csv(stats,out/'validation_statistics.csv')
    selected=select_service(stats,p['selection_target'])
    chosen=[x for x in specs if x['family']!='service_milp' or x['id']==selected['candidate']]
    frozen={'protocol':p,'fingerprint':signature,'candidates':specs,'selected':chosen,'service_selection':selected,
            'validation_ledger_max_error':error,'frozen_at':datetime.now(timezone.utc).isoformat(),
            'validation_files':{n:file_hash(out/n) for n in ['validation_episodes.csv','validation_cells.csv','validation_statistics.csv']}}
    write_json(out/'selection.json',frozen)
    print('One service tolerance frozen globally across all budgets and regimes.',flush=True)


def load_frozen(p,out):
    frozen=json.loads((out/'selection.json').read_text(encoding='utf-8'))
    if frozen['fingerprint']!=fingerprint(p):raise ValueError('Frozen inputs/source changed')
    if any(file_hash(out/n)!=h for n,h in frozen['validation_files'].items()):
        raise ValueError('Validation evidence changed after selection')
    return frozen


def test_stage(p,out):
    if (out/'test_episodes.csv').exists():raise FileExistsError('Test evidence already exists')
    frozen=load_frozen(p,out)
    df,error=run_grid(p,frozen['selected'],p['test_seeds'],out,'test')
    if frozen['fingerprint']!=fingerprint(p):raise ValueError('Inputs changed during testing')
    write_json(out/'test_verification.json',{'checks':'passed','episodes':len(df),'ledger_max_error':error,
        'selection_sha256':file_hash(out/'selection.json'),
        'files':{n:file_hash(out/n) for n in ['test_episodes.csv','test_channels.csv','representative_daily.csv']}})


def summarize(df,p):
    result=[]
    for (resource,regime,family,candidate),g in df.groupby(['resource','regime','family','candidate']):
        row={'resource':resource,'regime':regime,'family':family,'candidate':candidate,'n':len(g)}
        for metric in METRICS:
            row[metric],row[metric+'_ci95_low'],row[metric+'_ci95_high']=interval(g[metric])
        for profile in p['report_profiles']:
            row[profile['name']+'_mean_pass']=bool(row['fill_rate']>=profile['fill'] and row['worst_channel_fill']>=profile['worst'])
            row[profile['name']+'_episode_violation_rate']=float(((g.fill_rate<profile['fill'])|(g.worst_channel_fill<profile['worst'])).mean())
        for key in ['fallback_days','limit_days','service_primary_unproven_days','service_primary_precision_unmet_days','service_refinement_fallback_days']:
            row[key]=int(g[key].sum())
        row['mean_solve_seconds']=float(g.mean_solve_seconds.mean())
        result.append(row)
    return pd.DataFrame(result)


def paired_effects(df,p):
    rows=[]
    for regime in p['regimes']:
        groups={(r,f):g.set_index('seed').sort_index() for (r,f),g in df[df.regime==regime].groupby(['resource','family'])}
        reference=next(iter(groups.values()))
        if any(not reference.index.equals(g.index) or not (reference.demand_sha256==g.demand_sha256).all() for g in groups.values()):
            raise ValueError('Unpaired factorial cells')
        def effect(label,terms):
            row={'regime':regime,'effect':label,'n':len(reference)}
            for metric in METRICS:
                values=sum(sign*groups[key][metric] for sign,key in terms)
                row[metric+'_difference'],row[metric+'_ci95_low'],row[metric+'_ci95_high']=interval(values)
            rows.append(row)
        for resource in ['base','budget_plus_10pct']:
            for comparator in ['stock','economic_milp']:
                effect(f'service_minus_{comparator}@{resource}',[(1,(resource,'service_milp')),(-1,(resource,comparator))])
        for family in ['stock','economic_milp','service_milp']:
            effect(f'budget_increment@{family}',[(1,('budget_plus_10pct',family)),(-1,('base',family))])
        effect('budget_by_service_interaction',[(1,('budget_plus_10pct','service_milp')),(-1,('base','service_milp')),
                                               (-1,('budget_plus_10pct','economic_milp')),(1,('base','economic_milp'))])
    return pd.DataFrame(rows)


def resource_bounds(df,p):
    rows=[]
    for resource in p['resources']:
        net=network_for(resource,{'network_overrides':{}})
        for regime in p['regimes']:
            for seed in p['test_seeds']:
                _,demand=synthetic_history(net,seed,p['days'],regime)
                bound=service_bound(net,demand,regime)
                observed=df[(df.resource==resource['name'])&(df.regime==regime)&(df.seed==seed)]
                if (observed.fill_rate>bound['aggregate_fill_upper_bound']+1e-9).any() or (observed.worst_channel_fill>bound['worst_channel_fill_upper_bound']+1e-9).any():
                    raise ValueError('Realized policy exceeded a necessary resource bound')
                rows.append({'resource':resource['name'],'regime':regime,'seed':seed,**bound})
    return pd.DataFrame(rows)


def plot_results(summary,out,p):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    colors={'stock':'#64748b','economic_milp':'#0369a1','service_milp':'#b45309'}
    markers={'base':'o','budget_plus_10pct':'s'}
    plt.rcParams.update({'svg.fonttype':'none','svg.hashsalt':'service-budget-v2'})
    for view in ['service','economics']:
        fig,axes=plt.subplots(1,len(p['regimes']),figsize=(15,4.7),sharex=True,sharey=True,squeeze=False,layout='constrained')
        for ax,regime in zip(axes[0],p['regimes']):
            for family,color in colors.items():
                g=summary[(summary.regime==regime)&(summary.family==family)].set_index('resource').loc[['base','budget_plus_10pct']]
                x=g.fill_rate*100 if view=='service' else g.worst_channel_fill*100
                y=g.worst_channel_fill*100 if view=='service' else g.economic_value/1000
                ax.plot(x,y,color=color,alpha=.55,linewidth=1)
                for i,resource in enumerate(['base','budget_plus_10pct']):
                    ax.scatter(x.iloc[i],y.iloc[i],color=color,marker=markers[resource],s=65)
            ax.set_title(regime)
            ax.set_xlabel('Aggregate fill / %' if view=='service' else 'Worst-channel fill / %')
            ax.set_ylabel('Worst-channel fill / %' if view=='service' else 'Economic value / thousand illustrative CNY')
            if view=='service':
                ax.axvline(p['selection_target']['fill']*100,color='#999999',linestyle='--',linewidth=.8)
                ax.axhline(p['selection_target']['worst']*100,color='#999999',linestyle='--',linewidth=.8)
            ax.grid(alpha=.2)
        handles=[Line2D([0],[0],color=c,label=f) for f,c in colors.items()]
        handles.extend(Line2D([0],[0],color='black',linestyle='none',marker=m,label=r) for r,m in markers.items())
        axes[0,0].legend(handles=handles,fontsize=8)
        fig.suptitle(f'Frozen policies on {len(p["test_seeds"])} paired held-out seeds per regime; lines connect budget conditions')
        fig.savefig(out/f'{view}.png',dpi=160);fig.savefig(out/f'{view}.svg')
        plt.close(fig)


def report_stage(p,out):
    frozen=load_frozen(p,out)
    verification=json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if verification['selection_sha256']!=file_hash(out/'selection.json') or any(file_hash(out/n)!=h for n,h in verification['files'].items()):
        raise ValueError('Frozen selection or held-out evidence changed')
    df=pd.read_csv(out/'test_episodes.csv',float_precision='round_trip')
    check_grid(df,p,frozen['selected'],p['test_seeds'])
    summary=summarize(df,p);effects=paired_effects(df,p);bounds=resource_bounds(df,p)
    write_csv(summary,out/'test_summary.csv');write_csv(effects,out/'paired_effects.csv');write_csv(bounds,out/'resource_bound_episodes.csv')
    bound_summary=bounds.groupby(['resource','regime'],as_index=False)[['aggregate_fill_upper_bound','worst_channel_fill_upper_bound']].mean()
    write_csv(bound_summary,out/'resource_bound_summary.csv')
    plot_results(summary,out,p)
    lines=['# Service priority and procurement budget', '',
        'All demand and logistics economics are synthetic. Controls were fixed from the prior study; one service tolerance is selected globally on fresh validation paths.',
        'Candidate counts and solver phases differ. Two-stage service priority uses half the per-decision solver limit for each phase; actual elapsed times are reported.', '',
        '## Frozen service choice', '', '```',json.dumps(frozen['service_selection'],indent=2),'```','',
        '## Held-out outcomes', '', '```',summary[['resource','regime','family','economic_value','fill_rate','worst_channel_fill','balanced_mean_pass','balanced_episode_violation_rate']].to_string(index=False),'```','',
        '## Paired policy, budget and interaction effects', '', '```',effects[['regime','effect','economic_value_difference','fill_rate_difference','worst_channel_fill_difference']].to_string(index=False),'```','',
        f'All differences have unadjusted paired Student-t 95% intervals in paired_effects.csv; n={len(p["test_seeds"])} seeds per regime. Do not pool regimes as independent replicates.',
        'Effects of budget compare unchanged policies on common demand paths. Interaction is the service-policy budget response minus the economic-MILP budget response.',
        'Changing the budget cap is hypothetical; economic value includes actual procurement costs but no extra financing or facility-reservation fee.', '',
        '## Optimistic ex-post resource bounds', '', '```',bound_summary.to_string(index=False),'```','',
        'These bounds relax distribution timing and capacities. They see demand after choices are frozen and are never inputs to a controller. Passing a bound is not proof of service feasibility.',
        'The service policy prioritizes forecast-conditioned cumulative channel service; it does not guarantee realized service. If primary optimality is unproven, the refinement cap uses its feasible incumbent, not the unknown optimum.',
        'Primary service precision is 0.001 absolute deficit units (0.1 percentage point). The precision certificate and exact optimality are reported separately; solver success at this tolerance is not exact optimality.',
        'The first service incumbent is retained if economic refinement has no valid solution; all such fallbacks are counted. If the primary phase fails, the existing feasible stock fallback applies.',
        'Further limits: one network, small fixed synthetic samples, uncensored demand, finite horizon/salvage, tuned tolerance conditional on validation, no multiple-comparison correction or production evidence.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    manifest={'fingerprint':frozen['fingerprint'],'python':platform.python_version(),
              'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','matplotlib']},
              'synthetic_data':True,'files':{f.name:file_hash(f) for f in sorted(out.iterdir()) if f.is_file() and f.name!='run_manifest.json'}}
    write_json(out/'run_manifest.json',manifest)
    print(f'Report: {out / "REPORT.md"}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/service_budget.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage',choices=['run','validate','test','report'],default='run')
    args=parser.parse_args()
    p=validate_protocol(json.loads(args.protocol.read_text(encoding='utf-8')))
    out=args.output.resolve()
    for reference in ['network','research','audit','service_frontier']:
        old=(ROOT/'results'/reference).resolve()
        if out==old or old in out.parents:parser.error('Use a fresh output outside prior reference studies')
    out.mkdir(parents=True,exist_ok=True)
    if args.stage in ['run','validate']:validate_stage(p,out)
    if args.stage in ['run','test']:test_stage(p,out)
    if args.stage in ['run','report']:report_stage(p,out)


if __name__=='__main__':main()
