import copy
import json
import unittest
from unittest.mock import patch
import numpy as np
from supplychain.forecast import safety_stock
from supplychain.network import Network, State, validate_action
from supplychain.planner import plan
from supplychain.research import variant, forecast_scores
from supplychain.simulation import run_episode
from test_network import tiny


class ResearchTests(unittest.TestCase):
    def test_reserve_zero_for_constant_and_increases_with_protection(self):
        constant = np.full((42, 1, 1), 5)
        self.assertEqual(safety_stock(constant).item(), 0)
        history = np.arange(42).reshape(42, 1, 1) % 9
        self.assertGreater(safety_stock(history, 4).item(), safety_stock(history, 1).item())
        self.assertGreaterEqual(safety_stock(history, quantile=.95).item(),
                                safety_stock(history, quantile=.8).item())

    def test_reserve_is_soft_when_inventory_unavailable(self):
        n = tiny()
        s = State.initial(n)
        s.warehouse[:] = 0
        a = plan(n, s, np.full((2, 1, 1), 2), safety=np.full((1, 1), 100))
        validate_action(n, s, a)
        self.assertLess(a.diagnostics['max_constraint_violation'], 1e-5)

    def test_safety_policy_has_no_future_access(self):
        n = tiny()
        first = []
        history = (np.arange(42).reshape(42, 1, 1) % 5)
        for future in [np.zeros((4, 1, 1), int), np.full((4, 1, 1), 50)]:
            with patch('supplychain.simulation.synthetic_history', return_value=(history, future)):
                r = run_episode(n, days=4, policy='mpc_safety', capture=True)
            first.append((r['decisions'][0]['orders'], r['decisions'][0]['shipments']))
            self.assertTrue(all(d['mass_balance_error'] == 0 for d in r['daily']))
        self.assertEqual(first[0], first[1])

    def test_parameter_variant_does_not_mutate_base(self):
        n = Network.load()
        original = copy.deepcopy(n.raw)
        v = variant(n, 'capacity', .7)
        self.assertEqual(n.raw, original)
        np.testing.assert_array_equal(v.warehouse_handling, np.floor(n.warehouse_handling*.7))
        np.testing.assert_array_equal(v.supplier_capacity, n.supplier_capacity)

    def test_reference_cells_have_identical_cache_keys(self):
        n = Network.load()
        keys = [json.dumps(variant(n, factor, value).raw, sort_keys=True)
                for factor, value in [('service_target', .8), ('holding_cost', 1.),
                                      ('shortage_cost', 1.), ('capacity', 1.)]]
        self.assertEqual(len(set(keys)), 1)

    def test_forecast_evaluation_scores_constant_demand_exactly(self):
        h = np.full((42, 1, 1), 3)
        f = np.full((7, 1, 1), 3)
        with patch('supplychain.research.synthetic_history', return_value=(h, f)):
            scores = forecast_scores(tiny(), [1], 7)
        self.assertTrue((scores.wape == 0).all())

    def test_episode_cost_reconciles(self):
        r = run_episode(tiny(), days=5, policy='mpc_safety')
        s = r['summary']
        expected = (s['revenue']-sum(s[k] for k in ['procurement','shipping','dispatch','holding','shortage_penalty'])
                    -s['initial_inventory_charge']+s['terminal_salvage'])
        self.assertAlmostEqual(s['economic_value'], expected)


if __name__ == '__main__':
    unittest.main()
