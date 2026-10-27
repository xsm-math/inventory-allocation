"""Ex-post optimistic service bounds from purchasing resources.

This diagnostic sees realized demand ONLY after choices have been frozen. It
relaxes shipment timing, network capacities and integrality. Failure of an upper
bound rules out a target; passing it never proves an implementable policy exists.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from supplychain.network import Network
from supplychain.forecast import synthetic_history


def service_bound(net, demand, regime='normal'):
    demand = np.asarray(demand, float)
    if (demand.ndim != 3 or demand.shape[1:] != (net.C, net.P) or not len(demand)
            or not np.isfinite(demand).all() or (demand < 0).any()):
        raise ValueError('Expected finite nonnegative day/channel/product demand')
    if regime not in {'normal', 'surge', 'supply_shock'}:
        raise ValueError('Unknown supply regime')
    days = len(demand)
    totals = demand.sum(axis=0)
    total = float(totals.sum())
    # Orders placed too late to arrive cannot support any in-episode sales.
    order_days = np.arange(max(0, days-net.supplier_lead))
    factors = np.where((order_days >= days//3) & (order_days < 2*days//3), .45, 1.) if regime == 'supply_shock' else np.ones(len(order_days))
    capacity = np.floor(factors[:,None]*net.supplier_capacity).sum(axis=0)
    budget = float(factors.sum()*net.procurement_budget)
    stock = net.warehouse_initial.sum(axis=0)+net.channel_initial.sum(axis=0)
    sold = np.arange(net.C*net.P).reshape(net.C, net.P)
    purchase = np.arange(net.C*net.P, net.C*net.P+net.P)
    alpha = int(purchase[-1])+1
    size = alpha+1
    a = []
    b = []
    for product in range(net.P):
        row = np.zeros(size)
        row[sold[:,product]] = 1.
        row[purchase[product]] = -1.
        a.append(row)
        b.append(stock[product])
    row = np.zeros(size)
    row[purchase] = net.unit_cost
    a.append(row)
    b.append(budget)
    for channel in range(net.C):
        row = np.zeros(size)
        row[sold[channel]] = -1.
        row[alpha] = totals[channel].sum()
        a.append(row)
        b.append(0.)
    bounds = [(0., float(v)) for v in totals.ravel()]+[(0., float(v)) for v in capacity]+[(0.,1.)]
    answers = []
    for metric in ['aggregate', 'worst_channel']:
        objective = np.zeros(size)
        if metric == 'aggregate':
            objective[sold.ravel()] = -1.
        else:
            objective[alpha] = -1.
        result = linprog(objective, A_ub=np.array(a), b_ub=np.array(b), bounds=bounds, method='highs')
        if not result.success:
            raise RuntimeError(f'Relaxed service bound failed: {result.message}')
        answers.append(float(-result.fun/total if metric == 'aggregate' and total else -result.fun if metric == 'worst_channel' else 1.))
    return {'aggregate_fill_upper_bound': min(1., answers[0]),
            'worst_channel_fill_upper_bound': min(1., answers[1]),
            'arriving_order_budget': budget,
            'demand': total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.run_dir.resolve()
    frozen = json.loads((out/'selection.json').read_text(encoding='utf-8'))
    p = frozen['protocol']
    rows = []
    base = Network.load()
    for scenario in ['base', 'budget_plus_10pct', 'supplier_plus_10pct']:
        raw = copy.deepcopy(base.raw)
        if scenario == 'budget_plus_10pct':
            raw['procurement_budget'] *= 1.1
        if scenario == 'supplier_plus_10pct':
            raw['supplier_capacity'] = np.floor(np.asarray(raw['supplier_capacity'])*1.1).astype(int).tolist()
        net = Network(raw)
        for regime in p['regimes']:
            for seed in p['test_seeds']:
                _, demand = synthetic_history(base, seed, p['days'], regime)
                rows.append({'scenario': scenario, 'regime': regime, 'seed': seed, **service_bound(net, demand, regime)})
    df = pd.DataFrame(rows)
    summary = df.groupby(['scenario','regime'], as_index=False).agg(
        aggregate_fill_upper_bound=('aggregate_fill_upper_bound','mean'),
        worst_channel_fill_upper_bound=('worst_channel_fill_upper_bound','mean'))
    df.to_csv(out/'capacity_bound_episodes.csv', index=False)
    summary.to_csv(out/'capacity_bound_summary.csv', index=False)
    checks = []
    for profile in p['service_profiles']:
        for row in summary[summary.scenario == 'base'].to_dict('records'):
            ruled_out = (row['aggregate_fill_upper_bound'] < profile['fill']-1e-10 or
                          row['worst_channel_fill_upper_bound'] < profile['worst']-1e-10)
            checks.append({'profile':profile['name'], **row, 'mean_target_ruled_out_by_bound':ruled_out})
    pd.DataFrame(checks).to_csv(out/'capacity_bound_target_checks.csv', index=False)
    # Independent objectives give separate necessary bounds, not a sufficient
    # joint feasibility certificate. Relaxations are recomputed for each path.
    text = ['# Ex-post optimistic purchasing-resource bounds', '',
            'Realized demand is used after validation selection is frozen; it is never supplied to a policy.',
            'Bounds relax network flow/timing and integer controls, retaining initial stock and arriving procurement quantity/budget.',
            'Aggregate fill and worst-channel fill are maximized separately. Passing both separate bounds is not sufficient for joint feasibility.',
            'A mean upper bound below a service target rules out that empirical mean target on these fixed demand paths even for a clairvoyant relaxed controller.',
            'Capacity increases here are hypothetical and affect optimistic bounds only; they do not estimate achievable operational gains or investment value.', '',
            '```', summary.to_string(index=False), '```', '', '```', pd.DataFrame(checks).to_string(index=False), '```']
    (out/'CAPACITY_BOUNDS.md').write_text('\n'.join(text)+'\n', encoding='utf-8')
    metadata = {'script_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
                'selection_sha256':hashlib.sha256((out/'selection.json').read_bytes()).hexdigest(),
                'protocol':p, 'diagnostic_only':True}
    (out/'capacity_bound_manifest.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()
