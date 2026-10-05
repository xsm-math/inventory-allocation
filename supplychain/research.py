"""Paired parameter experiments and past-only forecast evaluation."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import scipy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .network import Network
from .forecast import predict, synthetic_history
from .simulation import run_episode
from .benchmark import intervals

ROOT = Path(__file__).resolve().parents[1]


def variant(base, factor, value):
    raw = copy.deepcopy(base.raw)
    # Preserve scalar types at the reference level so identical experiments
    # share the same cache key (1 and 1.0 serialize differently in JSON).
    if factor in {'shortage_cost', 'holding_cost', 'capacity'} and value == 1:
        return Network(raw)
    keys = {'shortage_cost': ['shortage_penalty'],
            'holding_cost': ['warehouse_holding', 'channel_holding'],
            'capacity': ['warehouse_handling', 'lane_capacity']}
    if factor == 'service_target':
        raw['service_target'] = value
    else:
        for key in keys[factor]:
            array = np.asarray(raw[key])*value
            raw[key] = (np.floor(array).astype(int) if factor == 'capacity' else array).tolist()
    return Network(raw)


def forecast_scores(net, seeds, days):
    rows = []
    for regime in ['normal', 'surge', 'supply_shock']:
        for seed in seeds:
            history, future = synthetic_history(net, seed, days, regime)
            predictions = {'recent_mean': [], 'seasonal_naive': [], 'blended': []}
            for actual in future:
                predictions['recent_mean'].append(np.rint(history[-7:].mean(0)))
                predictions['seasonal_naive'].append(history[-7].copy())
                predictions['blended'].append(predict(history, 1)[0])
                history = np.concatenate([history, actual[None]])
            for method, estimates in predictions.items():
                error = np.asarray(estimates)-future
                rows.append(dict(regime=regime, seed=seed, method=method,
                                 mae=float(np.abs(error).mean()),
                                 wape=float(np.abs(error).sum()/future.sum()),
                                 bias=float(error.sum()/future.sum())))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, default=6)
    parser.add_argument('--days', type=int, default=21)
    parser.add_argument('--time-limit', type=float, default=2.)
    args = parser.parse_args()
    if args.seeds < 2 or args.days < 7:
        parser.error('At least two seeds and seven days required')
    out = ROOT/'results/research'
    out.mkdir(parents=True, exist_ok=True)
    net = Network.load()
    seeds = list(range(201, 201+args.seeds))
    # Separate from the main comparison seeds; no best-parameter selection.
    levels = {'service_target': [.6, .8, .95], 'shortage_cost': [.5, 1., 2.],
              'holding_cost': [.5, 1., 2.], 'capacity': [.7, 1., 1.3]}
    rows, cache = [], {}
    for factor, values in levels.items():
        for value in values:
            n = variant(net, factor, value)
            config_key = json.dumps(n.raw, sort_keys=True)
            for seed in seeds:
                for policy in ['base_stock', 'mpc_safety']:
                    key = (config_key, seed, policy)
                    if key not in cache:
                        cache[key] = run_episode(n, seed, args.days, 'normal', policy,
                                                 time_limit=args.time_limit)['summary']
                    rows.append(dict(factor=factor, level=value, **cache[key]))
            print(f'Sensitivity {factor}={value} complete', flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out/'sensitivity_episodes.csv', index=False)
    aggregates = []
    for (factor, level, policy), g in df.groupby(['factor', 'level', 'policy']):
        row = dict(factor=factor, level=level, policy=policy, n=len(g))
        for metric in ['economic_value', 'fill_rate', 'worst_channel_fill', 'holding',
                       'shortage_penalty', 'shipping', 'forecast_wape']:
            row[metric], row[metric+'_ci95'] = intervals(g[metric])
        row.update(fallback_days=int(g.fallback_days.sum()), limit_days=int(g.limit_days.sum()))
        aggregates.append(row)
    ag = pd.DataFrame(aggregates)
    ag.to_csv(out/'sensitivity_summary.csv', index=False)
    paired = []
    for (factor, level), g in df.groupby(['factor', 'level']):
        pivot = g.pivot(index='seed', columns='policy', values='economic_value')
        gain, ci = intervals(pivot.mpc_safety-pivot.base_stock)
        paired.append(dict(factor=factor, level=level, mean_gain=gain, ci95_halfwidth=ci))
    pd.DataFrame(paired).to_csv(out/'sensitivity_paired.csv', index=False)
    forecast_scores(net, range(101, 113), args.days).to_csv(out/'forecast_scores.csv', index=False)
    plt.rcParams.update({'svg.fonttype': 'none', 'svg.hashsalt': 'inventory-research'})
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout='constrained')
    for col, factor in enumerate(levels):
        for policy, color in [('base_stock', '#8795a5'), ('mpc_safety', '#b26b32')]:
            g = ag[(ag.factor == factor) & (ag.policy == policy)].sort_values('level')
            for row, metric in enumerate(['economic_value', 'fill_rate']):
                axes[row, col].errorbar(g.level, g[metric], yerr=g[metric+'_ci95'],
                                       label=policy, color=color, marker='o', capsize=3)
                axes[row, col].set_xlabel(factor)
                axes[row, col].grid(alpha=.2)
    axes[0, 0].set_ylabel('Economic value / CNY')
    axes[1, 0].set_ylabel('Realized fill rate')
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('One-factor sensitivity, normal demand; 95% seed-level t intervals')
    fig.savefig(out/'sensitivity.svg')
    plt.close(fig)
    manifest = {'python': platform.python_version(), 'numpy': np.__version__,
                'pandas': pd.__version__, 'scipy': scipy.__version__,
                'sensitivity_seeds': seeds, 'forecast_seeds': list(range(101,113)),
                'days': args.days, 'time_limit': args.time_limit,
                'unique_sensitivity_episodes': len(cache), 'levels': levels,
                'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                  for p in sorted((ROOT/'supplychain').glob('*.py'))},
                'config_sha256': hashlib.sha256((ROOT/'configs/network.json').read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
