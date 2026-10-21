"""Capacity, solver diagnostics and matched-lookahead audit regressions."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
from supplychain.network import Network, State, Action, validate_action
from supplychain.planner import Model, plan
from supplychain.policies import decide
from supplychain.simulation import run_episode
from test_network import tiny


class AuditTests(unittest.TestCase):
    def test_three_period_milp_matches_independent_physical_enumeration(self):
        raw=copy.deepcopy(tiny().raw)
        raw.update(warehouse_initial=[[2]],warehouse_handling=[2],supplier_capacity=[1],
                   procurement_budget=10,lane_capacity=[1,1])
        net=Network(raw)
        for demands in [(1,0,2),(0,2,1)]:
            best=[float('inf')];first_actions=set()
            # This oracle advances physical stocks and explicit lead-time queues;
            # it does not reuse the MILP matrix or the simulator's execute().
            def visit(day,w,c,q_due,q_next,g_due,sales,cost,first):
                if day==3:
                    total=cost-net.salvage_fraction*10*(w+c)+8*max(0,.8*sum(demands)-sales)
                    if total<best[0]-1e-8:best[0]=total;first_actions.clear()
                    if abs(total-best[0])<1e-8:first_actions.add(first)
                    return
                w+=q_due;c+=g_due
                for q in range(2 if day+2<3 else 1):
                    for ground in range(2 if day+1<3 else 1):
                        for express in range(2):
                            if ground+express>min(w,2):continue
                            sold=min(c+express,demands[day]);lost=demands[day]-sold
                            wn=w-ground-express;cn=c+express-sold
                            step=(10*q+ground+2.4*express+(2 if ground else 0)+(3 if express else 0)
                                  +.2*wn+.5*cn-20*sold+4*lost)
                            visit(day+1,wn,cn,q_next,q,ground,sales+sold,cost+step,
                                  (q,ground,express) if first is None else first)
            visit(0,2,0,0,0,0,0,0.,None)
            action=plan(net,State.initial(net),np.array(demands).reshape(3,1,1),gap=0)
            self.assertAlmostEqual(action.diagnostics['planning_objective'],best[0],places=6)
            control=(int(action.orders[0,0]),int(action.shipments[0,0,0,0]),int(action.shipments[0,0,1,0]))
            self.assertIn(control,first_actions)

    def test_invalid_supply_cannot_bypass_budget_or_capacity(self):
        net=tiny();state=State.initial(net);action=Action.zero(net);action.orders[:]=999
        for factor in [np.nan,np.inf,-.1,1.1,True]:
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                validate_action(net,state,action,factor)

    def test_optional_reserve_settings_validated_at_config_boundary(self):
        for key,value in [('safety_quantile',1.),('safety_quantile',np.nan),
                          ('safety_slack_penalty',-1.),('safety_slack_penalty',np.inf)]:
            raw=copy.deepcopy(tiny().raw);raw[key]=value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):Network(raw)

    def test_feasible_incumbent_without_gap_remains_usable_and_unknown(self):
        original=Model.solve
        def no_gap(model,*args):
            result,matrix=original(model,*args);result.mip_gap=None
            return result,matrix
        net=tiny()
        with patch.object(Model,'solve',no_gap):
            action=plan(net,State.initial(net),np.array([[[2]]]))
            self.assertIsNone(action.diagnostics['mip_gap'])
            validate_action(net,State.initial(net),action)
            episode=run_episode(net,days=3,policy='mpc')
            self.assertIsNone(episode['summary']['max_mip_gap'])
            self.assertEqual(episode['summary']['gap_observations'],0)

    def test_corrupt_incumbent_triggers_physical_fallback(self):
        original=Model.solve
        def corrupt(model,*args):
            result,matrix=original(model,*args);result.x[:]=-1
            return result,matrix
        net=tiny();state=State.initial(net)
        with patch.object(Model,'solve',corrupt):
            action=decide(net,state,np.full((14,1,1),2),0,4,'mpc')
        self.assertTrue(action.diagnostics['fallback'])
        validate_action(net,state,action)

    def test_matched_lookahead_is_explicit_and_does_not_change_demands(self):
        net=tiny();observed=[]
        from supplychain.policies import base_stock
        def record(net,state,forecast,*args):
            observed.append(len(forecast));return base_stock(net,state,forecast,*args)
        with patch('supplychain.policies.base_stock',side_effect=record):
            a=run_episode(net,days=7,policy='base_stock',horizon=3,baseline_horizon=3)
        b=run_episode(net,days=7,policy='base_stock',horizon=3)
        self.assertEqual(observed,[3,3,3,3,3,2,1])
        self.assertEqual(a['summary']['demand_sha256'],b['summary']['demand_sha256'])


if __name__=='__main__':unittest.main()
