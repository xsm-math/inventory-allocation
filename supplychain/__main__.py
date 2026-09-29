"""Run one reproducible network experiment and export the complete action trace."""
import argparse
import json
from pathlib import Path
from .network import Network
from .simulation import run_episode
from .policies import POLICIES

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path)
    p.add_argument('--policy',choices=POLICIES,default='mpc')
    p.add_argument('--regime',choices=['normal','surge','supply_shock'],default='normal')
    p.add_argument('--seed',type=int,default=101)
    p.add_argument('--days',type=int,default=21)
    p.add_argument('--horizon',type=int,default=5)
    p.add_argument('--output',type=Path,default=Path('results/network/episode.json'))
    a=p.parse_args()
    result=run_episode(Network.load(a.config),a.seed,a.days,a.regime,a.policy,a.horizon,capture=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result['summary'],indent=2))

if __name__=='__main__':main()
