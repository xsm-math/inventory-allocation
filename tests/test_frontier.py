"""Independent checks for service selection, paired evidence and tuned controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from supplychain.frontier import (ROOT, FAMILIES, validate_protocol, candidates,
    select_on_validation, validation_statistics, summarize_test, paired_comparisons,
    check_episodes, test_stage as execute_test_stage, write_json, source_hashes, digest)
from supplychain.network import Network, State, validate_action
from supplychain.policies import decide
from supplychain.simulation import run_episode
from test_network import tiny


def protocol():
    return json.loads((ROOT/'configs/service_frontier.json').read_text())


class FrontierTests(unittest.TestCase):
    def test_partitions_and_candidate_budgets_cannot_be_confounded(self):
        p = validate_protocol(protocol())
        specs = candidates(p)
        self.assertEqual([sum(x['family'] == f for x in specs) for f in FAMILIES], [9, 9, 9])
        self.assertEqual(len({x['id'] for x in specs}), 27)
        p['test_seeds'][0] = p['validation_seeds'][0]
        with self.assertRaises(ValueError):
            validate_protocol(p)

    def test_selection_prefers_eligible_then_value_and_exposes_infeasibility(self):
        # Expensive service is feasible; high-profit poor service cannot win.
        rows = []
        for family in FAMILIES:
            for suffix, value, fill, worst in [('bad', 1000., .7, .5), ('ok', 800., .9, .8), ('best', 850., .91, .81)]:
                rows.append(dict(candidate=family+'-'+suffix, family=family, mean_value=value, min_fill=fill, min_worst=worst))
        stats = pd.DataFrame(rows)
        profiles = [dict(name='feasible', fill=.9, worst=.8), dict(name='impossible', fill=.99, worst=.95)]
        chosen = select_on_validation(stats, profiles)
        self.assertTrue(all(x['candidate'].endswith('best') for x in chosen))
        self.assertEqual([x['validation_feasible'] for x in chosen], [True]*3+[False]*3)
        # Ordering of rows and unrelated held-out outcomes cannot affect choices.
        self.assertEqual(chosen, select_on_validation(stats.iloc[::-1], profiles))

    def test_global_selection_uses_the_weakest_regime_not_regime_oracle(self):
        records = []
        for family in FAMILIES:
            for seed in [1, 2]:
                for candidate in [family+'-a', family+'-b']:
                    for regime in ['normal', 'surge']:
                        poor = candidate.endswith('-a') and regime == 'surge'
                        records.append(dict(candidate=candidate, family=family, seed=seed, regime=regime,
                                            economic_value=1000 if candidate.endswith('-a') else 800,
                                            fill_rate=.7 if poor else .95, worst_channel_fill=.5 if poor else .9))
        _, stats = validation_statistics(pd.DataFrame(records))
        chosen = select_on_validation(stats, [dict(name='p', fill=.9, worst=.8)])
        self.assertTrue(all(x['candidate'].endswith('-b') for x in chosen))

    def test_test_stage_only_executes_frozen_choices(self):
        p = protocol()
        spec = candidates(p)[0]
        frozen = {'protocol': p, 'protocol_sha256': digest(p), 'source_sha256': source_hashes(),
                  'network_sha256': digest(Network.load().raw), 'candidates': candidates(p),
                  'selected': [{'candidate': spec['id']}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_json(out/'selection.json', frozen)
            with patch('supplychain.frontier.run_grid', return_value=(pd.DataFrame({'dummy':[1]}), 0.)) as run:
                with patch('supplychain.frontier.select_on_validation', side_effect=AssertionError('Test attempted selection')):
                    execute_test_stage(p, out)
            self.assertEqual(run.call_args.args[1], [spec])
            self.assertEqual(run.call_args.args[2], p['test_seeds'])
            changed = copy.deepcopy(p)
            changed['days'] += 1
            with self.assertRaises(ValueError):
                execute_test_stage(changed, out)

    def test_equal_profits_cannot_hide_service_loss_or_violations(self):
        p = protocol()
        p['regimes'] = ['normal']
        p['service_profiles'] = [dict(name='p', fill=.85, worst=.75)]
        selected = [dict(profile='p', family=f, candidate=f, validation_feasible=True) for f in (*FAMILIES, 'legacy_base_stock')]
        rows = []
        for family in (*FAMILIES, 'legacy_base_stock'):
            for seed in [1, 2, 3]:
                # Higher economic value but materially worse service for MILP.
                bad = family == 'milp'
                rows.append(dict(candidate=family, regime='normal', seed=seed, demand_sha256=str(seed),
                                 economic_value=200. if bad else 100., fill_rate=.86 if bad else .95,
                                 worst_channel_fill=.76 if bad else .9, shipping=1., dispatch=1., holding=1.,
                                 shortage_penalty=1., fallback_days=0, limit_days=0))
        frozen = {'protocol': p, 'selected': selected}
        result = paired_comparisons(pd.DataFrame(rows), frozen)
        milp = result[result.family == 'milp'].iloc[0]
        self.assertTrue(milp.both_test_mean_service_pass)
        self.assertFalse(milp.comparison_qualified)
        self.assertEqual(milp.status, 'service_condition_not_met')
        df = pd.DataFrame(rows)
        df.loc[(df.candidate == 'milp') & (df.seed == 1), 'worst_channel_fill'] = .1
        summary = summarize_test(df, frozen)
        self.assertAlmostEqual(summary[summary.family == 'milp'].iloc[0].episode_service_violation_rate, 1/3)

    def test_tuned_controls_remain_causal_feasible_and_legacy_compatible(self):
        n = tiny()
        original = run_episode(n, seed=91, days=5, policy='base_stock', capture=True)
        explicit = run_episode(n, seed=91, days=5, policy='base_stock', capture=True,
                               policy_options={'review_days':2, 'forecast_buffer':0., 'allocation_rule':'coverage'})
        self.assertEqual(original['decisions'], explicit['decisions'])
        history = np.full((42, 1, 1), 2)
        for rule in ['coverage', 'economic']:
            first = []
            for demand in [np.zeros((5,1,1), int), np.full((5,1,1), 40)]:
                with patch('supplychain.simulation.synthetic_history', return_value=(history, demand)):
                    r = run_episode(n, days=5, policy='base_stock', capture=True,
                                    policy_options={'review_days':4, 'forecast_buffer':.8, 'allocation_rule':rule})
                first.append(r['decisions'][0])
                self.assertTrue(all(x['mass_balance_error'] == 0 for x in r['daily']))
            self.assertEqual(first[0]['orders'], first[1]['orders'])
            self.assertEqual(first[0]['shipments'], first[1]['shipments'])
        for options in [{'review_days':0}, {'review_days':True}, {'allocation_rule':'unknown'}, {'forecast_buffer':np.nan}]:
            with self.assertRaises(ValueError):
                decide(n, State.initial(n), history, 0, 5, 'base_stock', **options)

    def test_pairing_and_ledger_checks_reject_corrupt_evidence(self):
        p = protocol()
        specs = candidates(p)[:2]
        rows = []
        for spec in specs:
            for seed in [1, 2]:
                rows.append(dict(candidate=spec['id'], family=spec['family'],
                    **run_episode(tiny(), seed=seed, days=3, policy='base_stock')['summary']))
        df = pd.DataFrame(rows)
        self.assertLess(check_episodes(df, specs, [1,2], ['normal']), 1e-7)
        corrupt = df.copy()
        corrupt.loc[0, 'economic_value'] += 1.
        with self.assertRaises(ValueError):
            check_episodes(corrupt, specs, [1,2], ['normal'])
        corrupt = df.copy()
        corrupt.loc[0, 'demand_sha256'] = 'unpaired'
        with self.assertRaises(ValueError):
            check_episodes(corrupt, specs, [1,2], ['normal'])

    def test_economic_rule_uses_scarce_stock_for_larger_contribution(self):
        raw = copy.deepcopy(tiny().raw)
        raw.update(channels=['low','high'], price=[[20],[50]], shortage_penalty=[[4],[4]],
                   mean_demand=[[1],[1]], channel_initial=[[0],[0]],
                   ground_lead=[[1,1]], ground_cost=[[1,1]], warehouse_initial=[[1]],
                   warehouse_handling=[1], lane_capacity=[1,1])
        n = Network(raw)
        history = np.ones((42,2,1), int)
        a = decide(n, State.initial(n), history, 0, 5, 'base_stock')
        b = decide(n, State.initial(n), history, 0, 5, 'base_stock', allocation_rule='economic')
        validate_action(n, State.initial(n), a)
        validate_action(n, State.initial(n), b)
        self.assertEqual(a.shipments[0,0,1,0], 1)
        self.assertEqual(b.shipments[0,1,1,0], 1)


if __name__ == '__main__':
    unittest.main()
