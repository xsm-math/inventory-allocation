import copy
import unittest
from unittest.mock import patch

import numpy as np

from supplychain.network import Network, State, validate_action
from supplychain.planner import Model, plan
from supplychain.policies import decide
from supplychain.simulation import run_episode
from test_network import tiny


def two_channels():
    raw=copy.deepcopy(tiny().raw)
    raw.update(channels=['low','high'], price=[[20],[50]], shortage_penalty=[[4],[4]],
               mean_demand=[[1],[1]], channel_initial=[[0],[0]], ground_lead=[[1,1]],
               ground_cost=[[1,1]], warehouse_initial=[[1]], warehouse_handling=[1],
               lane_capacity=[1,1])
    return Network(raw)


def control(tolerance=0.):
    return dict(demand=np.array([4.,4.]), sold=np.array([0.,4.]), goal=.9, tolerance=tolerance)


class ServicePolicyTests(unittest.TestCase):
    def test_service_incumbent_matches_independent_one_unit_enumeration(self):
        n=two_channels(); d=np.ones((1,2,1),int)
        actions=[]
        for low,high in [(0,0),(1,0),(0,1)]:
            gap=max(0.,.9-min(low/5,(4+high)/5))
            actions.append((gap,low,high))
        best=min(x[0] for x in actions)
        action=plan(n,State.initial(n),d,service_control=control(),gap=0.)
        validate_action(n,State.initial(n),action)
        self.assertAlmostEqual(action.diagnostics['service_primary_incumbent_deficit'],best)
        self.assertAlmostEqual(action.diagnostics['service_primary_bound'],best)
        self.assertEqual(action.shipments[0,0,1,0],1)
        self.assertEqual(action.shipments[0,1,1,0],0)

    def test_economic_refinement_respects_declared_service_tolerance(self):
        n=two_channels(); d=np.ones((1,2,1),int)
        strict=plan(n,State.initial(n),d,service_control=control(),gap=0.)
        relaxed=plan(n,State.initial(n),d,service_control=control(.25),gap=0.)
        self.assertEqual(strict.shipments[0,0,1,0],1)
        self.assertEqual(relaxed.shipments[0,1,1,0],1)
        self.assertGreater(relaxed.diagnostics['service_deficit_cap'],strict.diagnostics['service_deficit_cap'])
        self.assertLess(relaxed.diagnostics['planning_objective'],strict.diagnostics['planning_objective'])

    def test_observed_service_debt_changes_allocation(self):
        n=two_channels(); observed=control(); observed['sold']=np.array([4.,0.])
        action=plan(n,State.initial(n),np.ones((1,2,1),int),service_control=observed)
        self.assertEqual(action.shipments[0,1,1,0],1)

    def test_unavailable_stock_records_unavoidable_shortfall(self):
        n=tiny();state=State.initial(n);state.warehouse[:]=0
        c=dict(demand=[0.],sold=[0.],goal=.9,tolerance=0.)
        action=plan(n,state,np.full((1,1,1),2),service_control=c)
        self.assertEqual(action.shipments.sum(),0)
        self.assertAlmostEqual(action.diagnostics['service_primary_incumbent_deficit'],.9)
        self.assertAlmostEqual(action.diagnostics['service_projected_min_fill'],0.)

    def test_failed_or_corrupt_refinement_uses_checked_service_incumbent(self):
        original=Model.solve
        for corrupt in [False,True]:
            calls=[]
            def failed(model,*args):
                result,matrix=original(model,*args);calls.append(1)
                if len(calls)==2:
                    result.status=1
                    if corrupt:result.x[:]=-1
                    else:result.x=None;result.fun=None
                return result,matrix
            n=two_channels()
            with patch.object(Model,'solve',failed):
                action=plan(n,State.initial(n),np.ones((1,2,1),int),service_control=control())
            self.assertTrue(action.diagnostics['service_refinement_fallback'])
            self.assertTrue(action.diagnostics['fallback'])
            self.assertIsNone(action.diagnostics['mip_gap'])
            self.assertEqual(action.shipments[0,0,1,0],1)
            validate_action(n,State.initial(n),action)

    def test_failed_primary_uses_physical_stock_fallback(self):
        n=tiny();history=np.full((42,1,1),2)
        with patch('supplychain.policies.plan',side_effect=RuntimeError('No service incumbent')):
            action=decide(n,State.initial(n),history,0,5,'mpc_service',
                          service_history={'demand':[0.],'sold':[0.]})
        self.assertTrue(action.diagnostics['fallback'])
        validate_action(n,State.initial(n),action)

    def test_primary_timeout_is_not_hidden_by_successful_refinement(self):
        original=Model.solve;calls=[]
        def unproven(model,*args):
            result,matrix=original(model,*args);calls.append(1)
            if len(calls)%2==1:result.status=1
            return result,matrix
        with patch.object(Model,'solve',unproven):
            result=run_episode(tiny(),days=3,policy='mpc_service')
        self.assertEqual(result['summary']['service_primary_unproven_days'],3)
        self.assertEqual(result['summary']['limit_days'],3)

    def test_service_precision_certificate_is_distinct_from_exact_optimality(self):
        original=Model.solve;calls=[]
        def approximate(model,*args):
            result,matrix=original(model,*args);calls.append(args)
            if len(calls)==1:result.mip_dual_bound=result.fun-.0005
            return result,matrix
        n=two_channels()
        with patch.object(Model,'solve',approximate):
            action=plan(n,State.initial(n),np.ones((1,2,1),int),service_control=control())
        self.assertEqual(calls[0][2],.001)
        self.assertTrue(action.diagnostics['service_primary_precision_met'])
        self.assertFalse(action.diagnostics['service_primary_exact'])
        self.assertAlmostEqual(action.diagnostics['service_primary_absolute_gap'],.0005)

    def test_simulator_passes_only_pre_decision_prefix_and_is_causal(self):
        n=tiny();history=np.full((42,1,1),2)
        futures=[np.full((6,1,1),2),np.array([2,2,2,40,40,40]).reshape(6,1,1)]
        runs=[]
        for future in futures:
            with patch('supplychain.simulation.synthetic_history',return_value=(history,future)):
                r=run_episode(n,days=6,policy='mpc_service',capture=True,
                              policy_options={'forecast_buffer':.8,'service_tolerance':.02})
            runs.append(r)
            for day,decision in enumerate(r['decisions']):
                self.assertEqual(decision['observed_channel_demand'],[int(future[:day].sum())])
                self.assertEqual(decision['observed_channel_sold'],[sum(x['sold'] for x in r['daily'][:day])])
        for day in range(4):
            for key in ['orders','shipments','observed_channel_demand','observed_channel_sold']:
                self.assertEqual(runs[0]['decisions'][day][key],runs[1]['decisions'][day][key])

    def test_invalid_history_and_ignored_service_knobs_fail_closed(self):
        n=tiny();d=np.full((1,1,1),2)
        good=dict(demand=[2.],sold=[1.],goal=.9,tolerance=.02)
        for changes in [dict(demand=[np.nan]),dict(sold=[3.]),dict(sold=[-1.]),
                        dict(demand=[1.,2.]),dict(goal=1.1),dict(tolerance=-.1),dict(goal=True),dict(precision=-.001)]:
            with self.assertRaises(ValueError):
                plan(n,State.initial(n),d,service_control={**good,**changes})
        for policy in ['base_stock','mpc']:
            with self.assertRaises(ValueError):
                decide(n,State.initial(n),np.full((42,1,1),2),0,5,policy,service_tolerance=.02)


if __name__=='__main__':unittest.main()
