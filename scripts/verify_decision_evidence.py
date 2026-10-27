"""Fast integrity, pairing and accounting audit of a completed decision study."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from supplychain.decision_study import load_frozen,candidates,assess_choices
from supplychain.service_budget import file_hash,check_grid,write_json
from supplychain.forecast import synthetic_history
from supplychain.network import Network


def verify(out):
    out=Path(out);p=json.loads((out/'selection.json').read_text(encoding='utf-8'))['protocol']
    frozen=load_frozen(p,out)
    manifest=json.loads((out/'run_manifest.json').read_text(encoding='utf-8'))
    for name,sha in manifest['files'].items():
        if file_hash(out/name)!=sha:raise ValueError(f'Artifact bytes changed: {name}')
    if manifest['fingerprint']!=frozen['fingerprint']:raise ValueError('Manifest fingerprint changed')
    for script,key in [('decision_diagnostics.py','report_postprocessor_sha256')]:
        actual=hashlib.sha256((ROOT/'scripts'/script).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=manifest[key]:raise ValueError('Diagnostic source changed')
    v=json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if v['selection_sha256']!=file_hash(out/'selection.json'):raise ValueError('Frozen selection changed')
    maximum_error=0.;counts={};net=Network.load()
    keys=['candidate','resource','regime','seed']
    for stage in ['validation','test']:
        episodes=pd.read_csv(out/f'{stage}_episodes.csv',float_precision='round_trip')
        daily=pd.read_csv(out/f'{stage}_daily.csv',float_precision='round_trip')
        channels=pd.read_csv(out/f'{stage}_channels.csv',float_precision='round_trip')
        maximum_error=max(maximum_error,check_grid(episodes,p,candidates(p),p[f'{stage}_seeds']))
        if daily.duplicated(keys+['day']).any() or not (daily.groupby(keys).size()==p['days']).all():raise ValueError('Incomplete daily keys')
        if channels.duplicated(keys+['channel']).any() or not (channels.groupby(keys).size()==net.C).all():raise ValueError('Incomplete channel keys')
        if len(daily)!=len(episodes)*p['days'] or len(channels)!=len(episodes)*net.C:raise ValueError('Incomplete evidence counts')
        if daily.mass_balance_error.max()!=0:raise ValueError('Recorded mass balance failed')
        costs=['procurement','shipping','dispatch','holding','shortage_penalty']
        error=(daily.revenue-daily[costs].sum(1)-daily.operating_value).abs().max()
        maximum_error=max(maximum_error,float(error))
        agg=daily.groupby(keys).agg(value=('operating_value','sum'),sold=('sold','sum'),demand=('demand','sum'))
        ep=episodes.set_index(keys).loc[agg.index]
        error=(agg.value-ep.initial_inventory_charge+ep.terminal_salvage-ep.economic_value).abs().max()
        maximum_error=max(maximum_error,float(error))
        if (agg.sold!=ep.sold).any() or (agg.demand!=ep.demand).any():raise ValueError('Daily totals changed')
        service=daily[daily.candidate=='service_milp']
        if not service.service_warm_start_submitted.all():raise ValueError('Missing checked service start')
        if (service.planning_objective>service.service_warm_start_economic_objective+1e-6).any():raise ValueError('Refinement regression')
        for regime in p['regimes']:
            for seed in p[f'{stage}_seeds']:
                _,demand=synthetic_history(net,seed,p['days'],regime)
                sha=hashlib.sha256(demand.tobytes()).hexdigest()
                if not (episodes[(episodes.seed==seed)&(episodes.regime==regime)].demand_sha256==sha).all():
                    raise ValueError('Regenerated demand does not match paired paths')
        counts[stage]={'episodes':len(episodes),'daily_rows':len(daily),'channel_rows':len(channels)}
    if maximum_error>1e-7:raise ValueError('Accounting failed')
    # Recompute the held-out assessment using the persisted validation choices.
    assessed=assess_choices(episodes,p,frozen['decisions'])
    saved=pd.read_csv(out/'decision_assessment.csv',float_precision='round_trip')
    for col in ['mandate','status']:
        if not (assessed[col]==saved[col]).all():raise ValueError('Decision assessment changed')
    for col in ['test_net_worst_regime_value','robust_value_difference','robust_difference_ci95_low','robust_difference_ci95_high']:
        np.testing.assert_allclose(assessed[col],saved[col],rtol=0,atol=1e-7,equal_nan=True)
    return {'checks':'passed','source_and_artifact_hashes':True,'regenerated_common_demand':True,
        'frozen_decisions_recomputed':True,'ledger_max_error':maximum_error,'counts':counts,
        'scope':'Recorded evidence integrity; not an independent rerun of every MILP decision.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=verify(args.run_dir)
    if args.output:write_json(args.output,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
