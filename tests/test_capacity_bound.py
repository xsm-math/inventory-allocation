import copy
import unittest
import numpy as np
from scripts.capacity_bound import service_bound
from supplychain.network import Network
from supplychain.forecast import synthetic_history
from supplychain.simulation import run_episode
from test_network import tiny


class CapacityBoundTests(unittest.TestCase):
    def test_hand_computed_budget_bound(self):
        raw = copy.deepcopy(tiny().raw)
        raw.update(warehouse_initial=[[0]], channel_initial=[[0]], procurement_budget=10)
        # Three days, two-day procurement lead: one arriving order, one unit
        # affordable at cost 10, against six units of demand.
        result = service_bound(Network(raw), np.full((3,1,1), 2))
        self.assertAlmostEqual(result['aggregate_fill_upper_bound'], 1/6)
        self.assertAlmostEqual(result['worst_channel_fill_upper_bound'], 1/6)

    def test_late_orders_cannot_raise_upper_bound(self):
        raw = copy.deepcopy(tiny().raw)
        raw.update(warehouse_initial=[[0]], channel_initial=[[0]], procurement_budget=10000)
        result = service_bound(Network(raw), np.full((2,1,1), 2))
        self.assertEqual(result['aggregate_fill_upper_bound'], 0.)
        self.assertEqual(result['worst_channel_fill_upper_bound'], 0.)

    def test_realized_feasible_policies_cannot_exceed_relaxed_bound(self):
        n = tiny()
        for regime in ['normal','surge','supply_shock']:
            _, demand = synthetic_history(n, 42, 9, regime)
            bound = service_bound(n, demand, regime)
            for policy in ['base_stock','mpc']:
                result = run_episode(n, seed=42, days=9, regime=regime, policy=policy)['summary']
                self.assertLessEqual(result['fill_rate'], bound['aggregate_fill_upper_bound']+1e-9)
                self.assertLessEqual(result['worst_channel_fill'], bound['worst_channel_fill_upper_bound']+1e-9)

    def test_zero_demand_and_invalid_input(self):
        result = service_bound(tiny(), np.zeros((3,1,1)))
        self.assertEqual(result['aggregate_fill_upper_bound'], 1.)
        self.assertEqual(result['worst_channel_fill_upper_bound'], 1.)
        for bad in [np.full((3,1,1), np.nan), np.full((3,1,1), -1), np.ones((3,2,1))]:
            with self.assertRaises(ValueError):
                service_bound(tiny(), bad)


if __name__ == '__main__':
    unittest.main()
