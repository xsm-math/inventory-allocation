"""Verify a complete reproduction, reconcile costs and add matched-horizon baselines."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from supplychain.network import Network
from supplychain.simulation import run_episode
from supplychain.benchmark import intervals


def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,default=ROOT/'results/reproduced')
    parser.add_argument('--output',type=Path,default=ROOT/'results/audit-generated')
    args=parser.parse_args();run_dir=args.run_dir.resolve();out=args.output.resolve()
    manifest=json.loads((run_dir/'run_manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['source_sha256'].items():
        require(hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest,f'Source differs: {name}')
    require(hashlib.sha256((ROOT/'configs/network.json').read_bytes()).hexdigest()==manifest['config_sha256'],'Config differs.')
    metadata=json.loads((run_dir/'network/metadata.json').read_text())
    df=pd.read_csv(run_dir/'network/episodes.csv')
    require(not df.duplicated(['regime','seed','policy']).any(),'Repeated episode keys.')
    require(len(df)==len(metadata['seeds'])*3*4,'Incomplete comparison.')
    require((df.groupby(['regime','seed']).policy.nunique()==4).all(),'Policies missing.')
    require((df.groupby(['regime','seed']).demand_sha256.nunique()==1).all(),'Unpaired demand paths.')
    require(np.isfinite(df.economic_value).all(),'Nonfinite values.')
    ledger=df.revenue-df[['procurement','shipping','dispatch','holding','shortage_penalty']].sum(axis=1)-df.initial_inventory_charge+df.terminal_salvage
    max_error=float(np.abs(ledger-df.economic_value).max())
    require(np.allclose(ledger,df.economic_value,rtol=0,atol=1e-7),'Cost ledger mismatch.')
    net=Network.load();matched=[];comparisons=[]
    for regime in ['normal','surge','supply_shock']:
        for seed in metadata['seeds']:
            r=run_episode(net,seed,metadata['days'],regime,'base_stock',horizon=metadata['horizon'],
                          time_limit=metadata['time_limit_seconds'],baseline_horizon=metadata['horizon'])['summary']
            original=df[(df.regime==regime)&(df.seed==seed)&(df.policy=='base_stock')].iloc[0]
            require(r['demand_sha256']==original.demand_sha256,'Matched baseline demand differs.')
            matched.append(r)
    new_base=pd.DataFrame(matched)
    for regime in ['normal','surge','supply_shock']:
        for basis,base in [('legacy',df[(df.regime==regime)&(df.policy=='base_stock')]),
                           ('matched_horizon',new_base[new_base.regime==regime])]:
            base=base.set_index('seed').sort_index()
            for name in ['mpc','mpc_buffered','mpc_safety']:
                p=df[(df.regime==regime)&(df.policy==name)].set_index('seed').sort_index()
                require(p.index.equals(base.index),'Episode seeds differ.')
                gain,halfwidth=intervals(p.economic_value-base.economic_value)
                comparisons.append({'regime':regime,'baseline':basis,'policy':name,'n':len(base),
                    'mean_paired_gain':gain,'ci95_halfwidth':halfwidth,'relative_gain':gain/base.economic_value.mean(),
                    'baseline_mean_value':base.economic_value.mean(),'policy_mean_value':p.economic_value.mean(),
                    'baseline_fill_rate':base.fill_rate.mean(),'policy_fill_rate':p.fill_rate.mean()})
    out.mkdir(parents=True,exist_ok=True)
    new_base.to_csv(out/'matched_baseline_episodes.csv',index=False)
    pd.DataFrame(comparisons).to_csv(out/'matched_comparisons.csv',index=False)
    result={'checks':'passed','main_episodes':len(df),'additional_matched_baseline_episodes':len(matched),
            'max_ledger_error':max_error,'config_sha256':manifest['config_sha256'],
            'source_sha256':manifest['source_sha256'],
            'scope':'Same synthetic inputs and policy settings; only base-stock lookahead matched. No new parameter selection or empirical business validation.',
            'interval':'Seed-paired t intervals, no multiple-testing correction.'}
    (out/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(pd.DataFrame(comparisons).to_string(index=False))


if __name__=='__main__':main()
