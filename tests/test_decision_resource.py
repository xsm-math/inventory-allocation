from types import SimpleNamespace
import unittest
import numpy as np
from scripts.decision_diagnostics import required_budget_lower_bound


def network(stock=0,capacity=100,cost=10,budget=50):
    return SimpleNamespace(C=1,P=1,supplier_lead=0,supplier_capacity=np.array([capacity]),
        procurement_budget=budget,warehouse_initial=np.array([[stock]]),channel_initial=np.array([[0]]),
        unit_cost=np.array([cost]))


class NecessaryBudgetTests(unittest.TestCase):
    def test_hand_computed_ninety_percent_budget(self):
        lower=required_budget_lower_bound(network(),np.full((3,1,1,1),10),'normal',.9,.8)
        self.assertAlmostEqual(lower,1.8)

    def test_initial_inventory_can_remove_budget_need(self):
        lower=required_budget_lower_bound(network(stock=10),np.full((2,1,1,1),10),'normal',.9,.8)
        self.assertEqual(lower,0.)

    def test_quantity_capacity_can_rule_out_even_unlimited_budget(self):
        lower=required_budget_lower_bound(network(capacity=5),np.full((2,1,1,1),10),'normal',.9,.8)
        self.assertIsNone(lower)

    def test_mean_gate_is_not_a_per_episode_gate(self):
        demand=np.array([10,100]).reshape(2,1,1,1)
        lower=required_budget_lower_bound(network(cost=1,budget=10,capacity=200),demand,'normal',.9,.8)
        self.assertAlmostEqual(lower,8.)


if __name__=='__main__':unittest.main()
