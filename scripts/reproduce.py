"""Run the complete experiment without overwriting committed reference results."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def source_hashes():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for p in sorted((ROOT/'supplychain').glob('*.py'))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/reproduced')
    args=parser.parse_args();out=args.output.resolve()
    for reference in [ROOT/'results/network',ROOT/'results/research']:
        if out==reference or reference in out.parents:
            parser.error('Choose a new output directory; reference results are preserved.')
    out.mkdir(parents=True,exist_ok=True)
    commands=[['-m','unittest','discover','-s','tests','-v'],
              ['-m','supplychain.benchmark','--seeds','12','--days','21','--output',str(out/'network')],
              ['-m','supplychain.research','--seeds','6','--days','21','--output',str(out/'research')],
              ['-m','supplychain.scaling','--output',str(out/'network/scaling.csv')]]
    records=[]
    for command in commands:
        started=time.monotonic()
        subprocess.run([sys.executable,*command],cwd=ROOT,check=True)
        records.append({'args':command,'exit_code':0,'seconds':time.monotonic()-started})
    manifest={'python':platform.python_version(),
              'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','matplotlib']},
              'source_sha256':source_hashes(),'commands':records,
              'config_sha256':hashlib.sha256((ROOT/'configs/network.json').read_bytes()).hexdigest(),
              'results':'Synthetic demand; seed-level paired comparisons, not business profit.',
              'files':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ['run_manifest.json','REPORT.md']}}
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    import pandas as pd
    paired=pd.read_csv(out/'network/paired_comparisons.csv')
    lines=['# Reproduction results','',
           'Complete 12-seed / 3-regime / 4-policy comparison, sensitivity, forecast and scale studies.',
           'Synthetic economic value; service trade-offs remain part of the decision.',
           '', '```',paired.to_string(index=False),'```','',
           'Intervals use 12 paired episode differences per regime. No multiple-comparison correction.',
           'The legacy base-stock coverage window differs from the MILP horizon; run scripts/audit.py for the matched control.',
           'Unknown or inapplicable solver gaps are blank/null, never evidence of zero-gap optimality.',
           'All input/code hashes and successful commands are in run_manifest.json.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Reproduction report: {out / "REPORT.md"}')


if __name__=='__main__':main()
