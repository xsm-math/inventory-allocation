import copy
import itertools
import unittest
from unittest.mock import patch
import numpy as np
from supplychain.network import Network, State, Action, validate_action
from supplychain.forecast import predict, synthetic_history
from supplychain.planner import plan
from supplychain.policies import decide
from supplychain.simulation import execute, run_episode


def tiny():
    raw=copy.deepcopy(Network.load().raw)
    raw.update(warehouses=['W'],channels=['C'],products=['P'],unit_cost=[10],volume=[1],price=[[20]],shortage_penalty=[[4]],mean_demand=[[2]],warehouse_initial=[[3]],channel_initial=[[0]],warehouse_handling=[3],supplier_capacity=[4],ground_lead=[[1]],ground_cost=[[1]],warehouse_holding=[.2],channel_holding=[.5],lane_capacity=[3,3],dispatch_fixed_cost=[2,3],procurement_budget=40,supplier_lead=2,service_target=.8,service_slack_penalty=8.)
    return Network(raw)

class NetworkTests(unittest.TestCase):
    def test_milp_matches_independent_enumeration(self):
        n=tiny();s=State.initial(n)
        for demand in [0,1,2,5]:
            a=plan(n,s,np.array([[[demand]]]),gap=0)
            costs=[]
            for units in range(4):
                sold=min(demand,units);lost=demand-sold
                cost=(units*n.freight[0,0,1]+(3 if units else 0)+.2*(3-units)+.5*(units-sold)
                      -20*sold+4*lost-8*(3-sold)+8*max(0,.8*demand-sold))
                costs.append(cost)
            self.assertAlmostEqual(a.diagnostics['planning_objective'],min(costs),places=5)
            self.assertEqual(a.orders.sum(),0)
    def test_lead_time_and_mass_conservation(self):
        n=tiny();s=State.initial(n);a=Action.zero(n)
        a.orders[0,0]=2;a.shipments[0,0,0,0]=2
        r,_,_=execute(n,s,a,0,np.array([[3]]))
        self.assertEqual(r['sold'],0)
        self.assertEqual(s.total_by_product()[0],5)
        s.receive(1);self.assertEqual(s.channel[0,0],2)
        self.assertEqual(s.warehouse[0,0],1)
        s.receive(2);self.assertEqual(s.warehouse[0,0],3)
    def test_shared_budget_and_lane_capacity(self):
        n=Network.load();s=State.initial(n)
        a=Action.zero(n);a.orders[:]=n.supplier_capacity
        with self.assertRaises(ValueError):validate_action(n,s,a)
        a=Action.zero(n);a.shipments[0,0,1,0]=20
        with self.assertRaises(ValueError):validate_action(n,s,a)
    def test_sparse_model_constraints(self):
        n=Network.load();s=State.initial(n)
        train,_=synthetic_history(n,7,3)
        a=plan(n,s,predict(train,5),supply_factor=.45)
        validate_action(n,s,a,.45)
        self.assertLess(a.diagnostics['max_constraint_violation'],1e-5)
    def test_forced_no_incumbent_falls_back(self):
        n=tiny();s=State.initial(n);history=np.full((14,1,1),2)
        with patch('supplychain.policies.plan',side_effect=RuntimeError('No feasible incumbent')):
            a=decide(n,s,history,0,10,'mpc')
        self.assertTrue(a.diagnostics['fallback']);validate_action(n,s,a)
    def test_no_future_demand_access(self):
        n=tiny();history=np.full((14,1,1),2);first=[]
        for future in [np.zeros((3,1,1),int),np.full((3,1,1),50)]:
            with patch('supplychain.simulation.synthetic_history',return_value=(history,future)):
                result=run_episode(n,days=3,policy='mpc',capture=True)
            first.append((result['decisions'][0]['orders'],result['decisions'][0]['shipments']))
        self.assertEqual(first[0],first[1])
    def test_replicated_demands_shared_between_policies(self):
        n=tiny()
        a=run_episode(n,days=3,policy='mpc');b=run_episode(n,days=3,policy='base_stock')
        self.assertEqual(a['summary']['demand_sha256'],b['summary']['demand_sha256'])
        self.assertTrue(all(r['mass_balance_error']==0 for r in a['daily']+b['daily']))
    def test_invalid_network_and_forecast(self):
        raw=copy.deepcopy(tiny().raw);raw['volume']=[0]
        with self.assertRaises(ValueError):Network(raw)
        with self.assertRaises(ValueError):predict(np.zeros((2,1,1)),2)
        with self.assertRaises(ValueError):plan(tiny(),State.initial(tiny()),np.array([[[np.nan]]]))

if __name__=='__main__':unittest.main()
