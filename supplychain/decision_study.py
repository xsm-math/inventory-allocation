"""Frozen, regime-robust policy/resource decisions under explicit service mandates.

All inputs are synthetic. Service gates are episode means, never SLA guarantees.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.metadata
import hashlib
import itertools
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
from scipy.stats import beta

from .frontier import ROOT, digest, interval
from .service_budget import (write_json, write_csv, file_hash, fingerprint as prior_fingerprint,
    network_for, check_grid, resource_bounds)
from .simulation import run_episode


def fingerprint(p):
    return {**prior_fingerprint(p), 'requirements':hashlib.sha256((ROOT/'requirements-lock.txt').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'native_solver_version':importlib.metadata.version('highspy')}


def validate_protocol(p):
    parts=['validation_seeds','test_seeds']
    for key in parts:
        if len(p[key])<2 or len(set(p[key]))!=len(p[key]) or any(type(x) is not int or x<0 for x in p[key]):
            raise ValueError('Invalid seed partition')
    if set(p[parts[0]]) & set(p[parts[1]]):raise ValueError('Overlapping partitions')
    old=json.loads((ROOT/'configs/service_budget.json').read_text(encoding='utf-8'))
    seen=set(sum([v for k,v in old.items() if k.endswith('_seeds')],[]))
    if seen & set(p[parts[0]]+p[parts[1]]):raise ValueError('Reused development paths')
    if p['regimes']!=['normal','surge','supply_shock']:raise ValueError('Declare all three regimes')
    if p['resources']!=[{'name':'base','budget_multiplier':1.}, {'name':'budget_plus_10pct','budget_multiplier':1.1}]:
        raise ValueError('This design compares base and budget +10%')
    for key in ['days','horizon','workers','bootstrap_samples']:
        if type(p[key]) is not int or p[key]<1:raise ValueError('Invalid experiment size')
    for key in ['time_limit','economic_precision']:
        if isinstance(p[key],bool) or not np.isfinite(p[key]) or p[key]<=0:raise ValueError('Invalid solve precision/time')
    if not p['fees_per_day'] or len(set(p['fees_per_day']))!=len(p['fees_per_day']) or any(not np.isfinite(x) or x<0 for x in p['fees_per_day']):
        raise ValueError('Invalid hypothetical facility fees')
    if len({x['name'] for x in p['mandates']})!=len(p['mandates']) or not p['mandates']:raise ValueError('Invalid mandates')
    for x in p['mandates']:
        if not 0<=x['worst']<=x['fill']<=1:raise ValueError('Invalid mandate threshold')
    for k in ['economic_certified_fraction','primary_certified_fraction']:
        if not 0<=p[k]<=1:raise ValueError('Invalid solver quality gate')
    return p


def candidates(p):
    common={'forecast_buffer':.8,'solver_backend':'highs','economic_precision':p['economic_precision']}
    return [
        {'id':'stock','family':'stock','policy':'base_stock','options':{'review_days':4,'forecast_buffer':0.},'network_overrides':{}},
        {'id':'economic_milp','family':'economic_milp','policy':'mpc','options':common.copy(),'network_overrides':{'service_slack_penalty':32.}},
        {'id':'service_milp','family':'service_milp','policy':'mpc_service',
         'options':{**common,'service_goal':.9,'service_tolerance':.02,'service_precision':.001},
         'network_overrides':{'service_slack_penalty':32.}}]


def run_cell(p,resource,regime,seed):
    rows=[];daily=[];channels=[]
    for spec in candidates(p):
        r=run_episode(network_for(resource,spec),seed=seed,days=p['days'],regime=regime,
                      policy=spec['policy'],horizon=p['horizon'],time_limit=p['time_limit'],policy_options=spec['options'])
        identity={'candidate':spec['id'],'family':spec['family'],'resource':resource['name'],'regime':regime,'seed':seed}
        rows.append({**identity,**r['summary']})
        daily.extend({**identity,**x} for x in r['daily'])
        channels.extend({**identity,**x} for x in r['channels'])
    return rows,daily,channels


def run_grid(p,seeds,out,stage):
    rows=[];daily=[];channels=[]
    with ProcessPoolExecutor(max_workers=p['workers']) as pool:
        jobs={pool.submit(run_cell,p,r,g,s):(r['name'],g,s)
              for r,g,s in itertools.product(p['resources'],p['regimes'],seeds)}
        for job in as_completed(jobs):
            a,b,c=job.result();rows.extend(a);daily.extend(b);channels.extend(c)
            write_csv(pd.DataFrame(rows),out/f'{stage}_progress.csv')
            print(f'{stage}: {jobs[job]}; {len(rows)} episodes',flush=True)
    keys=['resource','regime','seed','candidate']
    df=pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)
    error=check_grid(df,p,candidates(p),seeds)
    dd=pd.DataFrame(daily).sort_values(keys+['day']).reset_index(drop=True)
    if len(dd)!=len(df)*p['days'] or dd.duplicated(keys+['day']).any():raise ValueError('Daily evidence incomplete')
    if dd.mass_balance_error.max()!=0:raise ValueError('Inventory mass balance failed')
    # Every native service refinement starts from a checked feasible solution.
    service=dd[(dd.family=='service_milp') & dd.service_warm_start_submitted.fillna(False)]
    if (service.planning_objective>service.service_warm_start_economic_objective+1e-6).any():
        raise ValueError('Economic refinement worsened its service incumbent')
    write_csv(df,out/f'{stage}_episodes.csv');write_csv(dd,out/f'{stage}_daily.csv')
    write_csv(pd.DataFrame(channels).sort_values(keys+['channel']),out/f'{stage}_channels.csv')
    (out/f'{stage}_progress.csv').unlink()
    return df,error


def cells(df):
    rows=[]
    for (candidate,resource,regime),g in df.groupby(['candidate','resource','regime']):
        d=float(g.days.sum())
        rows.append({'candidate':candidate,'resource':resource,'regime':regime,'n':len(g),
            'value':float(g.economic_value.mean()),'fill':float(g.fill_rate.mean()),'worst':float(g.worst_channel_fill.mean()),
            'economic_certified_fraction':1-float(g.economic_precision_unmet_days.sum())/d,
            'primary_certified_fraction':1-float(g.service_primary_precision_unmet_days.sum())/d,
            'fallback_days':int(g.fallback_days.sum()),'mean_solve_seconds':float(g.mean_solve_seconds.mean())})
    return pd.DataFrame(rows)


def option_statistics(c,p,mandate):
    rows=[]
    for (candidate,resource),g in c.groupby(['candidate','resource']):
        service=bool((g.fill>=mandate['fill']-1e-12).all() and (g.worst>=mandate['worst']-1e-12).all())
        quality=bool((g.economic_certified_fraction>=p['economic_certified_fraction']-1e-12).all()
                     and (g.primary_certified_fraction>=p['primary_certified_fraction']-1e-12).all() and g.fallback_days.sum()==0)
        rows.append({'candidate':candidate,'resource':resource,'eligible':service and quality,
            'service_eligible':service,'quality_eligible':quality,'worst_regime_value':float(g.value.min()),
            'min_fill':float(g.fill.min()),'min_worst':float(g.worst.min()),
            'economic_certified_fraction':float(g.economic_certified_fraction.min()),
            'primary_certified_fraction':float(g.primary_certified_fraction.min())})
    return rows


def rank_options(stats,p,fee):
    ranked=[]
    for row in stats:
        if not row['eligible']:continue
        extra=row['resource']!='base'
        ranked.append({**row,'fee_per_day':fee,'net_worst_regime_value':row['worst_regime_value']-extra*p['days']*fee})
    order={'stock':0,'economic_milp':1,'service_milp':2}
    return sorted(ranked,key=lambda x:(-x['net_worst_regime_value'],order[x['candidate']],x['resource']!='base',x['resource']))


def freeze_choices(c,p):
    decisions=[];eligibility=[];thresholds=[]
    for mandate in p['mandates']:
        stats=option_statistics(c,p,mandate)
        eligibility.extend({'mandate':mandate['name'],**s} for s in stats)
        rank=rank_options(stats,p,0)
        base=next((x for x in rank if x['resource']=='base'),None)
        extra=next((x for x in rank if x['resource']!='base'),None)
        thresholds.append({'mandate':mandate['name'],'base_candidate':base['candidate'] if base else None,
            'extra_candidate':extra['candidate'] if extra else None,
            'validation_switch_fee_per_day':(extra['worst_regime_value']-base['worst_regime_value'])/p['days'] if base and extra else None})
        for fee in p['fees_per_day']:
            ordered=rank_options(stats,p,fee)
            decisions.append({'mandate':mandate['name'],'fee_per_day':fee,
                'status':'frozen' if ordered else 'no_supported_option',
                'selected':ordered[0] if ordered else None,'runner_up':ordered[1] if len(ordered)>1 else None})
    return decisions,eligibility,thresholds


def evidence_files(out,stage):
    return {n:file_hash(out/n) for n in [f'{stage}_episodes.csv',f'{stage}_daily.csv',f'{stage}_channels.csv']}


def validate_stage(p,out):
    if any(out.iterdir()):raise FileExistsError('Validation requires an empty output directory')
    sig=fingerprint(p);df,error=run_grid(p,p['validation_seeds'],out,'validation')
    if sig!=fingerprint(p):raise ValueError('Source changed during validation')
    c=cells(df);write_csv(c,out/'validation_cells.csv')
    decisions,eligibility,thresholds=freeze_choices(c,p)
    write_csv(pd.DataFrame(eligibility),out/'validation_eligibility.csv')
    write_csv(pd.DataFrame(thresholds),out/'validation_fee_thresholds.csv')
    write_json(out/'selection.json',{'protocol':p,'fingerprint':sig,'candidates':candidates(p),
        'frozen_at':datetime.now(timezone.utc).isoformat(),'decisions':decisions,
        'validation_ledger_max_error':error,'validation_files':{**evidence_files(out,'validation'),
            **{n:file_hash(out/n) for n in ['validation_cells.csv','validation_eligibility.csv','validation_fee_thresholds.csv']}}})
    print('Policy/resource choices frozen before held-out simulation.',flush=True)


def load_frozen(p,out):
    f=json.loads((out/'selection.json').read_text(encoding='utf-8'))
    if f['fingerprint']!=fingerprint(p) or f['protocol']!=p:raise ValueError('Frozen inputs/source changed')
    if any(file_hash(out/n)!=h for n,h in f['validation_files'].items()):raise ValueError('Validation evidence changed')
    return f


def test_stage(p,out):
    if (out/'test_episodes.csv').exists():raise FileExistsError('Held-out evidence already exists')
    frozen=load_frozen(p,out);df,error=run_grid(p,p['test_seeds'],out,'test')
    if frozen['fingerprint']!=fingerprint(p):raise ValueError('Source changed during held-out simulation')
    write_json(out/'test_verification.json',{'episodes':len(df),'ledger_max_error':error,
        'selection_sha256':file_hash(out/'selection.json'),'files':evidence_files(out,'test')})


def failure_upper(k,n,confidence=.95):
    """Exact one-sided binomial upper bound; independent episodes within a regime."""
    if not 0<=k<=n or n<1:raise ValueError('Invalid binomial sample')
    return 1. if k==n else float(beta.ppf(confidence,k+1,n-k))


def paired_robust_difference(a,b,bootstrap_samples=2000,seed=742):
    """Bootstrap paired seed rows, retaining all regimes and both frozen options."""
    a=np.asarray(a,float);b=np.asarray(b,float)
    if a.shape!=b.shape or a.ndim!=2 or len(a)<2:raise ValueError('Unpaired robust comparison')
    draws=np.random.default_rng(seed).integers(0,len(a),size=(bootstrap_samples,len(a)))
    diffs=a[draws].mean(1).min(1)-b[draws].mean(1).min(1)
    return float(a.mean(0).min()-b.mean(0).min()),*map(float,np.quantile(diffs,[.025,.975]))


def option_array(df,option,p,fee):
    g=df[(df.candidate==option['candidate']) & (df.resource==option['resource'])]
    v=g.pivot(index='seed',columns='regime',values='economic_value').reindex(index=p['test_seeds'],columns=p['regimes'])
    if v.isna().any().any():raise ValueError('Incomplete paired option')
    return v.to_numpy()-p['days']*fee*(option['resource']!='base')


def assess_choices(df,p,decisions):
    c=cells(df);rows=[]
    for d in decisions:
        row={'mandate':d['mandate'],'fee_per_day':d['fee_per_day'],'status':d['status']}
        if d['selected'] is None:rows.append(row);continue
        chosen=d['selected'];mandate=next(x for x in p['mandates'] if x['name']==d['mandate'])
        stat=next(x for x in option_statistics(c,p,mandate) if x['candidate']==chosen['candidate'] and x['resource']==chosen['resource'])
        row.update(candidate=chosen['candidate'],resource=chosen['resource'],test_mean_service_pass=stat['service_eligible'],
                   test_solver_quality_pass=stat['quality_eligible'],test_min_fill=stat['min_fill'],test_min_worst=stat['min_worst'])
        row['status']='test_mean_supported' if stat['eligible'] else ('test_service_not_confirmed' if not stat['service_eligible'] else 'test_solver_quality_not_confirmed')
        a=option_array(df,chosen,p,d['fee_per_day']);row['test_net_worst_regime_value']=float(a.mean(0).min())
        if d['runner_up']:
            other=d['runner_up'];b=option_array(df,other,p,d['fee_per_day'])
            delta,lo,hi=paired_robust_difference(a,b,p['bootstrap_samples'])
            row.update(runner_up_candidate=other['candidate'],runner_up_resource=other['resource'],
                robust_value_difference=delta,robust_difference_ci95_low=lo,robust_difference_ci95_high=hi)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df,p):
    rows=[]
    for (candidate,resource,regime),g in df.groupby(['candidate','resource','regime']):
        row={'candidate':candidate,'resource':resource,'regime':regime,'n':len(g)}
        for metric in ['economic_value','fill_rate','worst_channel_fill']:
            row[metric],row[metric+'_ci95_low'],row[metric+'_ci95_high']=interval(g[metric])
        for mandate in p['mandates']:
            k=int(((g.fill_rate<mandate['fill'])|(g.worst_channel_fill<mandate['worst'])).sum())
            row[mandate['name']+'_failed_episodes']=k
            row[mandate['name']+'_failure_probability_upper95']=failure_upper(k,len(g))
        for key in ['fallback_days','limit_days','economic_precision_unmet_days','service_primary_precision_unmet_days','service_primary_unproven_days','service_warm_start_submitted_days','service_start_retained_days']:
            row[key]=int(g[key].sum())
        row['mean_solve_seconds']=float(g.mean_solve_seconds.mean())
        rows.append(row)
    return pd.DataFrame(rows)


def report_stage(p,out):
    f=load_frozen(p,out);v=json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if v['selection_sha256']!=file_hash(out/'selection.json') or any(file_hash(out/n)!=h for n,h in v['files'].items()):
        raise ValueError('Held-out or frozen evidence changed')
    df=pd.read_csv(out/'test_episodes.csv',float_precision='round_trip')
    check_grid(df,p,candidates(p),p['test_seeds'])
    summary=summarize(df,p);assessment=assess_choices(df,p,f['decisions']);bounds=resource_bounds(df,p)
    write_csv(summary,out/'test_summary.csv');write_csv(cells(df),out/'test_cells.csv')
    write_csv(assessment,out/'decision_assessment.csv');write_csv(bounds,out/'resource_bound_episodes.csv')
    bound_summary=bounds.groupby(['resource','regime'],as_index=False).agg(
        mean_fill_upper=('aggregate_fill_upper_bound','mean'),max_fill_upper=('aggregate_fill_upper_bound','max'),
        mean_worst_upper=('worst_channel_fill_upper_bound','mean'))
    write_csv(bound_summary,out/'resource_bound_summary.csv')
    lines=['# Frozen decision study','',
        'Synthetic one-network study. Mandates and extra-budget facility fees are hypothetical inputs. Controllers never receive the realized regime label.',
        'Select once on validation: service and solver-quality gates in every regime; then maximize the minimum regime mean economic value less the facility fee. No held-out reselection.',
        'Fee is per operating day for access to the extra budget cap, not an extra procurement charge. Actual procurement is already charged in the ledger.', '',
        '## Frozen choices evaluated on held-out paths','','```',assessment.to_string(index=False),'```','',
        '## Policy/resource held-out means','','```',summary[['candidate','resource','regime','economic_value','fill_rate','worst_channel_fill','economic_precision_unmet_days']].to_string(index=False),'```','',
        '## Optimistic ex-post resource bounds','','```',bound_summary.to_string(index=False),'```','',
        'Bounds use future demand only for diagnosis and relax timing/lane/storage restrictions. An upper bound below a target excludes that target on those paths; exceeding the target does not establish feasibility.',
        'Per-metric mean Student-t intervals are unadjusted. Paired bootstrap intervals compare the robust scores of the frozen selected and runner-up options, resampling seed rows jointly across regimes; no option reselection. They are conditional on validation choices and the synthetic generator.',
        'Mean service gates are not hard episode guarantees. Exact one-sided binomial bounds in test_summary.csv expose the limited evidence for episode reliability.',
        'MILP economic certificates concern each forecast planning problem only: relative gap <=2% OR absolute gap <=25 illustrative CNY. Service primary precision is 0.001 deficit units. These do not certify realized policy optimality.',
        'All daily diagnostics and channel records are retained. Wall-clock time limits can change incumbents on other hardware; source, versions, common demand hashes and numerical invariants are recorded.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    write_json(out/'run_manifest.json',{'fingerprint':f['fingerprint'],'python':platform.python_version(),
        'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','highspy']},
        'synthetic_data':True,'files':{x.name:file_hash(x) for x in sorted(out.iterdir()) if x.is_file() and x.name!='run_manifest.json'}})
    print(f'Report: {out / "REPORT.md"}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/decision_study.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage',choices=['run','validate','test','report'],default='run')
    args=parser.parse_args();p=validate_protocol(json.loads(args.protocol.read_text(encoding='utf-8')))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.stage in ['run','validate']:validate_stage(p,out)
    if args.stage in ['run','test']:test_stage(p,out)
    if args.stage in ['run','report']:report_stage(p,out)


if __name__=='__main__':main()
