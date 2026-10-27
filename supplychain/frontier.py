"""Validation-frozen service/economic comparisons; no test-set policy selection.

Run ``python -m supplychain.frontier --stage run --output <fresh directory>``.
All demand is synthetic. Service gates concern empirical episode means, not
hard realized service guarantees or deployment approval.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.metadata
import itertools
import json
import platform

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from .network import Network
from .simulation import run_episode

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ('coverage_stock', 'economic_stock', 'milp')
LEDGER_COSTS = ('procurement', 'shipping', 'dispatch', 'holding', 'shortage_penalty')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted((ROOT/'supplychain').glob('*.py'))}


def validate_protocol(p):
    """Reject overlapping partitions and invalid gates before any experiments."""
    for name in ('development_seeds', 'validation_seeds', 'test_seeds'):
        values = p[name]
        if not values or any(type(v) is not int or v < 0 for v in values) or len(values) != len(set(values)):
            raise ValueError(f'Invalid or duplicate {name}')
    for a, b in itertools.combinations(('development_seeds', 'validation_seeds', 'test_seeds'), 2):
        if set(p[a]) & set(p[b]):
            raise ValueError(f'Overlapping {a}/{b}')
    if min(len(p['validation_seeds']), len(p['test_seeds'])) < 2:
        raise ValueError('At least two seeds per new partition')
    if (type(p['days']) is not int or p['days'] < 7 or type(p['horizon']) is not int or p['horizon'] < 1
            or isinstance(p['time_limit'], bool) or not np.isfinite(p['time_limit']) or p['time_limit'] <= 0):
        raise ValueError('Invalid experiment duration/solver settings')
    if not p['regimes'] or len(set(p['regimes'])) != len(p['regimes']) or set(p['regimes'])-{'normal', 'surge', 'supply_shock'}:
        raise ValueError('Invalid regimes')
    for key, low, high in (('buffers', 0., 2.), ('service_penalties', 0., np.inf)):
        values = p[key]
        if (not values or any(isinstance(v, bool) or not np.isfinite(v) or not low <= v <= high for v in values)
                or len(values) != len(set(values))):
            raise ValueError(f'Invalid {key}')
    if (not p['review_days'] or any(type(v) is not int or v < 1 for v in p['review_days'])
            or len(p['review_days']) != len(set(p['review_days']))):
        raise ValueError('Invalid review days')
    if len(p['review_days']) != len(p['service_penalties']):
        raise ValueError('Use the same candidate count for each family')
    profiles = p['service_profiles']
    if not profiles or len({x['name'] for x in profiles}) != len(profiles):
        raise ValueError('Service profiles must be nonempty and uniquely named')
    for profile in profiles:
        if not np.isfinite([profile['fill'], profile['worst']]).all() or not 0 <= profile['worst'] <= profile['fill'] <= 1:
            raise ValueError('Invalid service target')
    for key in ('fill', 'worst'):
        v = p['service_noninferiority_margins'][key]
        if isinstance(v, bool) or not np.isfinite(v) or not 0 <= v <= 1:
            raise ValueError('Invalid noninferiority margin')
    # This is the existing baseline's configuration, retained as a fixed control.
    if 2 not in p['review_days'] or 0. not in p['buffers']:
        raise ValueError('Candidate grid must contain the legacy control')
    return p


def candidates(p):
    result = []
    for rule, family in (('coverage', 'coverage_stock'), ('economic', 'economic_stock')):
        for review, buffer in itertools.product(p['review_days'], p['buffers']):
            result.append({'id': f'{family}-r{review}-b{buffer:g}', 'family': family,
                           'policy': 'base_stock', 'options': {'review_days': review,
                           'forecast_buffer': buffer, 'allocation_rule': rule}, 'network_overrides': {}})
    for penalty, buffer in itertools.product(p['service_penalties'], p['buffers']):
        result.append({'id': f'milp-s{penalty:g}-b{buffer:g}', 'family': 'milp', 'policy': 'mpc',
                       'options': {'forecast_buffer': buffer},
                       'network_overrides': {'service_slack_penalty': penalty}})
    return sorted(result, key=lambda x: x['id'])


def check_episodes(df, specs, seeds, regimes):
    keys = ['candidate', 'regime', 'seed']
    if df.duplicated(keys).any():
        raise ValueError('Duplicate episode keys')
    expected = set(itertools.product([s['id'] for s in specs], regimes, seeds))
    if set(map(tuple, df[keys].to_numpy())) != expected:
        raise ValueError('Episode coverage differs from the frozen plan')
    if (df.groupby(['regime', 'seed']).demand_sha256.nunique() != 1).any():
        raise ValueError('Policies did not receive paired demand paths')
    numeric = ['economic_value', 'fill_rate', 'worst_channel_fill', 'revenue',
               'initial_inventory_charge', 'terminal_salvage', *LEDGER_COSTS]
    if not np.isfinite(df[numeric].to_numpy(float)).all():
        raise ValueError('Nonfinite episode result')
    if not ((df[['fill_rate', 'worst_channel_fill']] >= 0) & (df[['fill_rate', 'worst_channel_fill']] <= 1)).all().all():
        raise ValueError('Invalid service result')
    identity = df.revenue-df[list(LEDGER_COSTS)].sum(axis=1)-df.initial_inventory_charge+df.terminal_salvage
    error = float((identity-df.economic_value).abs().max())
    if error > 1e-7:
        raise ValueError('Realized economic ledger did not reconcile')
    return error


def run_grid(p, specs, seeds, output, stage):
    base = Network.load()
    networks = {}
    for spec in specs:
        raw = copy.deepcopy(base.raw)
        # Tuning changes planning regularization, never realized ledger prices.
        raw.update(spec['network_overrides'])
        networks[spec['id']] = Network(raw)
    rows = []
    for regime in p['regimes']:
        for seed in seeds:
            for spec in specs:
                episode = run_episode(networks[spec['id']], seed=seed, days=p['days'], regime=regime,
                                      policy=spec['policy'], horizon=p['horizon'], time_limit=p['time_limit'],
                                      policy_options=spec['options'])
                rows.append({'candidate': spec['id'], 'family': spec['family'], **episode['summary']})
            pd.DataFrame(rows).to_csv(output/f'{stage}_progress.csv', index=False)
            print(f'{stage}: {regime} seed {seed}, {len(rows)} episodes', flush=True)
    df = pd.DataFrame(rows)
    error = check_episodes(df, specs, seeds, p['regimes'])
    df.to_csv(output/f'{stage}_episodes.csv', index=False)
    (output/f'{stage}_progress.csv').unlink()
    return df, error


def validation_statistics(df):
    by_regime = df.groupby(['candidate', 'family', 'regime'], as_index=False).agg(
        economic_value=('economic_value', 'mean'), fill=('fill_rate', 'mean'), worst=('worst_channel_fill', 'mean'))
    # Equal weight to each declared regime. Controllers do not observe a regime label.
    overall = by_regime.groupby(['candidate', 'family'], as_index=False).agg(
        mean_value=('economic_value', 'mean'), min_fill=('fill', 'min'), min_worst=('worst', 'min'))
    return by_regime, overall


def select_on_validation(stats, profiles):
    """Select globally across regimes. Test data cannot be passed to this API."""
    selected = []
    for profile in profiles:
        for family in FAMILIES:
            rows = stats[stats.family == family].copy()
            if rows.empty:
                raise ValueError('Missing candidate family')
            rows['service_deficit'] = np.maximum(np.maximum(profile['fill']-rows.min_fill, 0),
                                                np.maximum(profile['worst']-rows.min_worst, 0))
            eligible = rows[rows.service_deficit <= 1e-12]
            if len(eligible):
                chosen = eligible.sort_values(['mean_value', 'candidate'], ascending=[False, True]).iloc[0]
            else:
                chosen = rows.sort_values(['service_deficit', 'mean_value', 'candidate'],
                                          ascending=[True, False, True]).iloc[0]
            selected.append({'profile': profile['name'], 'family': family, 'candidate': chosen.candidate,
                             'validation_feasible': bool(len(eligible)),
                             'validation_min_fill': float(chosen.min_fill),
                             'validation_min_worst': float(chosen.min_worst),
                             'validation_mean_value': float(chosen.mean_value),
                             'validation_max_service_deficit': float(chosen.service_deficit)})
    return selected


def interval(values):
    a = np.asarray(values, float)
    if len(a) < 2 or not np.isfinite(a).all():
        raise ValueError('Intervals require at least two finite paired observations')
    mean = float(a.mean())
    half = float(student_t.ppf(.975, len(a)-1)*a.std(ddof=1)/np.sqrt(len(a)))
    return mean, mean-half, mean+half


def summarize_test(df, frozen):
    rows = []
    for chosen in frozen['selected']:
        target = next(x for x in frozen['protocol']['service_profiles'] if x['name'] == chosen['profile'])
        for regime in frozen['protocol']['regimes']:
            g = df[(df.candidate == chosen['candidate']) & (df.regime == regime)]
            row = {**chosen, 'regime': regime, 'n': len(g)}
            for key in ('economic_value', 'fill_rate', 'worst_channel_fill'):
                row[key], row[key+'_ci95_low'], row[key+'_ci95_high'] = interval(g[key])
            row['test_mean_service_pass'] = bool(row['fill_rate'] >= target['fill'] and row['worst_channel_fill'] >= target['worst'])
            row['episode_service_violation_rate'] = float(((g.fill_rate < target['fill']) | (g.worst_channel_fill < target['worst'])).mean())
            row['shipping_dispatch'] = float((g.shipping+g.dispatch).mean())
            row['holding'] = float(g.holding.mean())
            row['shortage_penalty'] = float(g.shortage_penalty.mean())
            row['fallback_days'] = int(g.fallback_days.sum())
            row['limit_days'] = int(g.limit_days.sum())
            rows.append(row)
    return pd.DataFrame(rows)


def paired_comparisons(df, frozen):
    rows = []
    p = frozen['protocol']
    selected = pd.DataFrame(frozen['selected'])
    for profile in p['service_profiles']:
        choices = selected[selected.profile == profile['name']].set_index('family')
        baseline = choices.loc['coverage_stock']
        for family in ('economic_stock', 'milp', 'legacy_base_stock'):
            chosen = choices.loc[family]
            for regime in p['regimes']:
                a = df[(df.candidate == chosen.candidate) & (df.regime == regime)].set_index('seed').sort_index()
                b = df[(df.candidate == baseline.candidate) & (df.regime == regime)].set_index('seed').sort_index()
                if not a.index.equals(b.index) or not (a.demand_sha256 == b.demand_sha256).all():
                    raise ValueError('Pairing failure')
                row = {'profile': profile['name'], 'regime': regime, 'family': family,
                       'candidate': chosen.candidate, 'baseline': baseline.candidate, 'n': len(a)}
                for key in ('economic_value', 'fill_rate', 'worst_channel_fill'):
                    row[key+'_difference'], row[key+'_ci95_low'], row[key+'_ci95_high'] = interval(a[key]-b[key])
                row['both_validation_feasible'] = bool(chosen.validation_feasible and baseline.validation_feasible)
                row['both_test_mean_service_pass'] = bool(
                    min(a.fill_rate.mean(), b.fill_rate.mean()) >= profile['fill'] and
                    min(a.worst_channel_fill.mean(), b.worst_channel_fill.mean()) >= profile['worst'])
                row['service_noninferiority_interval_pass'] = bool(
                    row['fill_rate_ci95_low'] >= -p['service_noninferiority_margins']['fill'] and
                    row['worst_channel_fill_ci95_low'] >= -p['service_noninferiority_margins']['worst'])
                qualified = all(row[k] for k in ('both_validation_feasible', 'both_test_mean_service_pass',
                                                 'service_noninferiority_interval_pass'))
                row['comparison_qualified'] = qualified
                row['status'] = ('service_condition_not_met' if not qualified else
                                 'exploratory_positive' if row['economic_value_ci95_low'] > 0 else
                                 'uncertain_or_nonpositive')
                rows.append(row)
    return pd.DataFrame(rows)


def validate_stage(p, out):
    if (out/'selection.json').exists() or (out/'test_episodes.csv').exists():
        raise FileExistsError('Choose a fresh directory; frozen selection/test evidence already exists')
    specs = candidates(p)
    df, error = run_grid(p, specs, p['validation_seeds'], out, 'validation')
    by_regime, stats = validation_statistics(df)
    by_regime.to_csv(out/'validation_by_regime.csv', index=False)
    stats.to_csv(out/'validation_selection_statistics.csv', index=False)
    selected = select_on_validation(stats, p['service_profiles'])
    control = stats.set_index('candidate').loc['coverage_stock-r2-b0']
    for profile in p['service_profiles']:
        selected.append({'profile': profile['name'], 'family': 'legacy_base_stock',
                         'candidate': 'coverage_stock-r2-b0',
                         'validation_feasible': bool(control.min_fill >= profile['fill'] and control.min_worst >= profile['worst']),
                         'validation_min_fill': float(control.min_fill), 'validation_min_worst': float(control.min_worst),
                         'validation_mean_value': float(control.mean_value),
                         'validation_max_service_deficit': float(max(0., profile['fill']-control.min_fill, profile['worst']-control.min_worst))})
    frozen = {'protocol': p, 'protocol_sha256': digest(p), 'source_sha256': source_hashes(),
              'network_sha256': digest(Network.load().raw), 'candidates': specs, 'selected': selected,
              'selection_rule': 'Eligible in every validation regime: maximize equal-regime mean value. Otherwise minimize maximum service deficit, then maximize value. Candidate id breaks ties.',
              'validation_ledger_max_error': error, 'frozen_at': datetime.now(timezone.utc).isoformat()}
    write_json(out/'selection.json', frozen)
    print('Validation choices frozen before test execution.', flush=True)
    return frozen


def load_frozen(p, out):
    frozen = json.loads((out/'selection.json').read_text(encoding='utf-8'))
    if frozen['protocol_sha256'] != digest(p) or frozen['source_sha256'] != source_hashes() or frozen['network_sha256'] != digest(Network.load().raw):
        raise ValueError('Protocol, source or network changed after validation; use a fresh run')
    return frozen


def test_stage(p, out):
    if (out/'test_episodes.csv').exists():
        raise FileExistsError('Test evidence exists; use report stage without rerunning selection')
    frozen = load_frozen(p, out)
    ids = {x['candidate'] for x in frozen['selected']}
    specs = [s for s in frozen['candidates'] if s['id'] in ids]
    df, error = run_grid(p, specs, p['test_seeds'], out, 'test')
    write_json(out/'test_verification.json', {'checks': 'passed', 'unique_test_episodes': len(df),
               'selected_unique_candidates': len(specs), 'test_ledger_max_error': error,
               'selection_file_sha256': hashlib.sha256((out/'selection.json').read_bytes()).hexdigest(),
               'protocol_sha256': digest(p), 'source_sha256': source_hashes()})
    return df, frozen


def report_stage(p, out):
    frozen = load_frozen(p, out)
    df = pd.read_csv(out/'test_episodes.csv', float_precision='round_trip')
    verification = json.loads((out/'test_verification.json').read_text(encoding='utf-8'))
    if verification['selection_file_sha256'] != hashlib.sha256((out/'selection.json').read_bytes()).hexdigest():
        raise ValueError('Frozen selection was modified after testing')
    specs = [s for s in frozen['candidates'] if s['id'] in {x['candidate'] for x in frozen['selected']}]
    check_episodes(df, specs, p['test_seeds'], p['regimes'])
    summary = summarize_test(df, frozen)
    paired = paired_comparisons(df, frozen)
    summary.to_csv(out/'test_summary.csv', index=False)
    paired.to_csv(out/'paired_comparisons.csv', index=False)
    plot_frontier(out, summary)
    lines = ['# Validation-frozen inventory service study', '',
             'Synthetic demand and illustrative CNY economics. No operational savings are established.', '',
             f"{len(frozen['candidates'])} validation candidates; {len(p['validation_seeds'])} validation and {len(p['test_seeds'])} test seeds per regime; {p['days']} operating days.",
             'Three families have equal candidate counts, not equal CPU tuning budgets. One global configuration per family/profile is selected across all validation regimes.',
             'Each baseline keeps its natural protection coverage. This compares complete policies, not a solver-only causal effect.', '',
             'Service gates apply to mean aggregate fill and mean episode-worst-channel fill in every validation regime. They do not guarantee every episode/channel or a future service probability.',
             'Ineligible choices use an explicitly labeled minimum-service-deficit fallback. Test violations are never removed or used to choose replacements.', '',
             '## Frozen choices', '', '```', pd.DataFrame(frozen['selected']).to_string(index=False), '```', '',
             '## All held-out test results', '', '```',
             summary[['profile','family','regime','economic_value','fill_rate','worst_channel_fill','episode_service_violation_rate','test_mean_service_pass']].to_string(index=False), '```', '',
             '## Paired comparisons against tuned coverage stock', '', '```',
             paired[['profile','family','regime','economic_value_difference','economic_value_ci95_low','economic_value_ci95_high','comparison_qualified','status']].to_string(index=False), '```', '',
             'A comparison is qualified only if both choices met validation targets, both test means meet the declared profile in that regime, and paired 95% lower bounds for service differences exceed the predeclared noninferiority margins.',
             'The positive label additionally requires a positive lower bound for economic value. These are exploratory, unadjusted intervals across multiple comparisons; they are not confirmatory superiority tests.', '',
             'Full service-difference intervals and diagnostics are retained in CSV. Episode accounting includes procurement, freight, dispatch, holding, shortage penalties, initial inventory charge and terminal salvage.',
             'Limits: one synthetic network; known uncensored demand; fixed five-day MILP horizon; finite 42-day experiment and salvage assumption; no independent real-world calibration.', '',
             '## Reproduce', '', '```bash',
             'python -m pip install -r requirements-lock.txt',
             'python -m unittest discover -s tests -v',
             'python -m supplychain.frontier --stage run --output results/service-frontier-new', '```',
             'Separate validate/test/report stages are supported. Use a fresh run directory to preserve evidence.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    manifest = {'protocol_sha256': digest(p), 'source_sha256': source_hashes(), 'network_sha256': frozen['network_sha256'],
                'python': platform.python_version(), 'packages': {n: importlib.metadata.version(n) for n in ('numpy','pandas','scipy','matplotlib')},
                'synthetic_data': True, 'frozen_at': frozen['frozen_at'],
                'files': {x.name: hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(out.iterdir()) if x.is_file() and x.name != 'run_manifest.json'}}
    write_json(out/'run_manifest.json', manifest)
    print(f'Report: {out / "REPORT.md"}', flush=True)


def plot_frontier(out, summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    validation = pd.read_csv(out/'validation_by_regime.csv')
    colors = {'coverage_stock':'#64748b','economic_stock':'#b45309','milp':'#0369a1','legacy_base_stock':'#8b5cf6'}
    regimes = list(validation.regime.unique())
    fig, axes = plt.subplots(2, len(regimes), figsize=(5*len(regimes), 8), squeeze=False, layout='constrained')
    for j, regime in enumerate(regimes):
        for family in FAMILIES:
            g = validation[(validation.regime == regime) & (validation.family == family)]
            axes[0,j].scatter(g.fill*100, g.economic_value/1000, label=family, c=colors[family], s=35)
        axes[0,j].set_title(regime+' / validation grid')
        for family in colors:
            g = summary[(summary.regime == regime) & (summary.family == family)].drop_duplicates('candidate')
            for _, row in g.iterrows():
                axes[1,j].scatter(row.fill_rate*100, row.economic_value/1000, c=colors[family], s=60,
                                  marker='o' if row.test_mean_service_pass else 'x')
        axes[1,j].set_title(regime+' / frozen test choices')
        for i in (0, 1):
            axes[i,j].set_xlabel('Aggregate fill rate / %')
            axes[i,j].set_ylabel('Episode economic value / thousand CNY')
            axes[i,j].grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Synthetic inventory: full validation grid and frozen test choices\nWorst-channel service and all profile violations are reported separately in CSV')
    fig.savefig(out/'service_economics.png', dpi=160)
    fig.savefig(out/'service_economics.svg')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT/'configs/service_frontier.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('run','validate','test','report'), default='run')
    args = parser.parse_args()
    p = validate_protocol(json.loads(args.protocol.read_text(encoding='utf-8')))
    out = args.output.resolve()
    for reference in (ROOT/'results/network', ROOT/'results/research', ROOT/'results/audit'):
        if out == reference or reference in out.parents:
            parser.error('Choose a new output directory outside the committed reference studies')
    out.mkdir(parents=True, exist_ok=True)
    if args.stage in ('run','validate'):
        validate_stage(p, out)
    if args.stage in ('run','test'):
        test_stage(p, out)
    if args.stage in ('run','report'):
        report_stage(p, out)


if __name__ == '__main__':
    main()
