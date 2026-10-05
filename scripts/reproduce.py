"""Run validation and the complete paper experiment with the current interpreter."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    for command in [['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                    ['-m', 'supplychain.benchmark', '--seeds', '12', '--days', '21'],
                    ['-m', 'supplychain.research', '--seeds', '6', '--days', '21'],
                    ['-m', 'supplychain.scaling'],
                    ['scripts/report.py']]:
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)
