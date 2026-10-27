"""Descriptive ledger attribution from verified held-out budget-study records."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from supplychain.frontier import interval
from supplychain.service_budget import write_csv,write_json,file_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    out=parser.parse_args().run_dir.resolve()
    verification=json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if (verification['files']['test_episodes.csv']!=file_hash(out/'test_episodes.csv')
            or verification['selection_sha256']!=file_hash(out/'selection.json')):
        raise ValueError('Held-out input/selection hash mismatch')
    frozen=json.loads((out/'selection.json').read_text(encoding='utf-8'))
    df=pd.read_csv(out/'test_episodes.csv',float_precision='round_trip')
    if df.duplicated(['resource','regime','family','seed']).any():raise ValueError('Duplicate factorial cells')
    components={'revenue':1,'procurement':-1,'shipping':-1,'dispatch':-1,
                'holding':-1,'shortage_penalty':-1,'initial_inventory_charge':-1,'terminal_salvage':1}
    attribution=[];funding=[]
    for regime in frozen['protocol']['regimes']:
        groups={(resource,family):g.set_index('seed').sort_index()
                for (resource,family),g in df[df.regime==regime].groupby(['resource','family'])}
        reference=next(iter(groups.values()))
        if any(not g.index.equals(reference.index) or not (g.demand_sha256==reference.demand_sha256).all() for g in groups.values()):
            raise ValueError('Unpaired diagnostics input')
        for resource in ['base','budget_plus_10pct']:
            a=groups[resource,'service_milp'];b=groups[resource,'economic_milp']
            delta=a.economic_value-b.economic_value
            contribution=pd.DataFrame({k:sign*(a[k]-b[k]) for k,sign in components.items()})
            error=float(np.max(np.abs(contribution.sum(axis=1)-delta)))
            if error>1e-7:raise ValueError('Attribution did not reconcile')
            mean,low,high=interval(delta)
            attribution.append({'resource':resource,'regime':regime,'n':len(a),
                **{k+'_contribution':float(contribution[k].mean()) for k in components},
                'economic_value_difference':mean,'ci95_low':low,'ci95_high':high,'max_identity_error':error})
        for family in ['stock','economic_milp','service_milp']:
            a=groups['budget_plus_10pct',family];b=groups['base',family]
            mean,low,high=interval(a.economic_value-b.economic_value)
            days=frozen['protocol']['days']
            funding.append({'family':family,'regime':regime,'n':len(a),'operating_days':days,
                'additional_actual_procurement':float((a.procurement-b.procurement).mean()),
                'incremental_value_per_operating_day':mean/days,
                'ci95_low_per_day':low/days,'ci95_high_per_day':high/days})
    write_csv(pd.DataFrame(attribution),out/'ledger_attribution.csv')
    write_csv(pd.DataFrame(funding),out/'budget_value_per_day.csv')
    write_json(out/'accounting_diagnostic_manifest.json',{
        'diagnostic_script_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'test_episodes_sha256':file_hash(out/'test_episodes.csv'),
        'selection_sha256':file_hash(out/'selection.json'),'descriptive_only':True})
    lines=['# Descriptive accounting diagnostics','',
           'Ledger contributions are service-priority minus economic-MILP, signed as contributions to economic value. Procurement, freight, dispatch, holding and shortage costs enter with minus signs; terminal salvage enters positively.',
           'Components are algebraic attribution on paired simulated paths, not independent causal effects or a minimum economic cost of fairness. The full identity is checked per seed.', '',
           '```',pd.DataFrame(attribution).to_string(index=False),'```','',
           'Incremental budget value per operating day is a deterministic rescaling of the declared paired budget effect, after actual procurement costs. It excludes financing and facility fees.',
           'A positive point estimate can be read as an illustrative break-even ceiling for an additional daily budget-facility fee under these assumptions. Unadjusted intervals crossing zero leave that benefit uncertain; negative values do not support paying a positive fee. No actual lending terms, risk-adjusted ROI or investment recommendation is inferred.', '',
           '```',pd.DataFrame(funding).to_string(index=False),'```']
    (out/'ACCOUNTING_DIAGNOSTICS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print('Verified ledger attribution and descriptive budget value per day written.')


if __name__=='__main__':main()
