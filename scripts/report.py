"""Generate publication tables directly from executed experiment outputs."""
from pathlib import Path
import json
import hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'base_stock': 'Base stock', 'mpc': 'Rolling MILP',
          'mpc_buffered': 'Buffered MILP', 'mpc_safety': 'Safety-stock MILP'}


def main():
    ag = pd.read_csv(ROOT/'results/network/aggregate.csv')
    ep = pd.read_csv(ROOT/'results/network/episodes.csv')
    pairs = pd.read_csv(ROOT/'results/network/paired_comparisons.csv')
    sensitivity = pd.read_csv(ROOT/'results/research/sensitivity_summary.csv')
    forecasts = pd.read_csv(ROOT/'results/research/forecast_scores.csv')
    manifest = json.loads((ROOT/'results/research/manifest.json').read_text())
    metadata = json.loads((ROOT/'results/network/metadata.json').read_text())
    assert manifest['config_sha256'] == metadata['config_sha256']
    assert manifest['config_sha256'] == hashlib.sha256((ROOT/'configs/network.json').read_bytes()).hexdigest()
    for name, expected in manifest['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected, f'Stale results: {name}'
    assert set(ep.policy) == set(LABELS)
    assert (ep.groupby(['regime', 'seed']).demand_sha256.nunique() == 1).all()
    lines = ['| Regime | Policy | Economic value (CNY) | Fill rate | Worst-channel fill |',
             '|---|---|---:|---:|---:|']
    for r in ag.itertuples():
        lines.append(f'| {r.regime} | {LABELS[r.policy]} | {r.economic_value:,.0f} | {r.fill_rate:.2%} | {r.worst_channel_fill:.2%} |')
    lines += ['', '| Regime | Policy vs. base stock | Paired gain (CNY) | 95% interval half-width | Relative gain |',
              '|---|---|---:|---:|---:|']
    for r in pairs.itertuples():
        lines.append(f'| {r.regime} | {LABELS[r.policy]} | {r.mean_paired_gain:,.0f} | {r.ci95_halfwidth:,.0f} | {r.relative_gain:.2%} |')
    lines += ['', f'Main study: {len(ep)} episodes; {int(ep.fallback_days.sum())} fallback days; '
              f'{int(ep.limit_days.sum())} time-limit days; maximum recorded MIP gap {ep.max_mip_gap.max():.2%}.',
              '', 'Paired, unadjusted Student-t intervals describe seed variation within the synthetic model. '
              'They do not establish real-world savings or guarantee service.']
    block = '\n'.join(lines)
    readme = ROOT/'README.md'
    text = readme.read_text(encoding='utf-8')
    before, rest = text.split('<!-- RESULTS:START -->')
    _, after = rest.split('<!-- RESULTS:END -->')
    readme.write_text(before+'<!-- RESULTS:START -->\n'+block+'\n<!-- RESULTS:END -->'+after, encoding='utf-8')
    report = ['# Executed research results', '', block, '', '## One-factor sensitivity', '',
              f"Normal regime; seeds {manifest['sensitivity_seeds']}; {manifest['unique_sensitivity_episodes']} unique episodes. "
              'Reference cells are reused, not additional independent observations.', '',
              '| Factor | Level | Policy | Economic value | Fill | Worst channel |',
              '|---|---:|---|---:|---:|---:|']
    for r in sensitivity.itertuples():
        report.append(f'| {r.factor} | {r.level:g} | {LABELS[r.policy]} | {r.economic_value:,.0f} | {r.fill_rate:.2%} | {r.worst_channel_fill:.2%} |')
    report += ['', '## Forecast evaluation', '',
               'Rolling one-day predictions use only observations before each decision. WAPE is averaged across seed-level ratios.', '',
               '| Regime | Method | Mean WAPE | Mean signed bias |', '|---|---|---:|---:|']
    for (regime, method), g in forecasts.groupby(['regime', 'method']):
        report.append(f'| {regime} | {method} | {g.wape.mean():.2%} | {g.bias.mean():.2%} |')
    report += ['', '## Interpretation boundaries', '',
               'Service and safety-stock targets are soft planning constraints, not realized service guarantees. '
               'Capacity sensitivity changes warehouse handling and transport lane capacities together, leaving procurement unchanged. '
               'Economic values under changed costs use those changed costs, so cross-setting changes are not pure policy-efficiency effects. '
               'Compare policies within each setting.', '',
               'Normal and supply-shock forecast scores match because their demand processes match. '
               'The blended predictor need not outperform the recent-mean comparator. No parameter was selected by maximizing these results.', '']
    (ROOT/'docs/research_results.md').write_text('\n'.join(report), encoding='utf-8')
    print('README tables and docs/research_results.md regenerated from CSV outputs.')


if __name__ == '__main__':
    main()
