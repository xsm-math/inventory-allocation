"""Reproduce the held-out comparison and demand-shift sensitivity."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from allocation import run_case
ROOT = Path(__file__).resolve().parent

def main():
    data = pd.read_csv(ROOT/'data/channels.csv')
    metrics, allocations, sensitivity, gains = [], [], [], []
    stocks = {'Camera-A': 620, 'Gimbal-B': 780}
    for sku, rows in data.groupby('sku', sort=False):
        rows = rows.reset_index(drop=True)
        case = run_case(rows, stocks[sku])
        metrics += [dict(sku=sku, **r) for r in case['metrics']]
        allocations += [dict(sku=sku, **r) for r in case['allocations']]
        gains.append(dict(sku=sku, **case['paired_gain']))
        for ratio in [.5, .7, .9, 1.1]:
            for scale in [.7, 1., 1.3]:
                result = run_case(rows, int(rows.forecast.sum()*ratio), scale=scale)
                sensitivity += [dict(sku=sku, stock_ratio=ratio, test_demand_scale=scale, **r) for r in result['metrics']]
    out = ROOT/'results'
    out.mkdir(exist_ok=True)
    df = pd.DataFrame(metrics)
    df.to_csv(out/'metrics.csv', index=False)
    pd.DataFrame(allocations).to_csv(out/'allocations.csv', index=False)
    pd.DataFrame(sensitivity).to_csv(out/'sensitivity.csv', index=False)
    (out/'paired_gain.json').write_text(json.dumps(gains, indent=2))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    colors = ['#91a4b7', '#e9ae56', '#267f80']
    for ax, (sku, group) in zip(axes, df.groupby('sku', sort=False)):
        ax.bar(['Proportional', 'Margin first', 'Optimized'], group.economic_value/1000, color=colors)
        ax.set(title=sku, ylabel='Expected economic value (thousand CNY)')
        for i, val in enumerate(group.economic_value/1000):
            ax.text(i, val, f'{val:.1f}', ha='center', va='bottom')
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Synthetic held-out demand | 2,000 scenarios | 25% allocation floor')
    fig.tight_layout()
    fig.savefig(out/'comparison.svg')
    print(df.to_string(index=False))
    print(json.dumps(gains, indent=2))

if __name__ == '__main__':
    main()
