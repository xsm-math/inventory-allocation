import copy
import itertools
import unittest

import numpy as np

from supplychain.planner import Model,checked_incumbent,plan
from supplychain.network import State,validate_action
from supplychain.simulation import run_episode
from test_network import tiny
from test_service_policy import two_channels,control


class NativeSolverTests(unittest.TestCase):
    def test_integer_optimum_matches_independent_enumeration(self):
        m=Model('highs');x=m.vars((3,),cost=[-3,-4,-5],upper=1,integer=True)
        m.constraint([(x,[1,2,3])],upper=3)
        r,A=m.solve(2.,0.)
        feasible=[sum(c*v for c,v in zip([-3,-4,-5],a)) for a in itertools.product([0,1],repeat=3)
                  if sum(w*v for w,v in zip([1,2,3],a))<=3]
        checked_incumbent(m,r,A)
        self.assertAlmostEqual(r.fun,min(feasible))
        self.assertEqual(r.status,0)

    def test_checked_start_is_preserved_even_with_zero_search_time(self):
        m=Model('highs');x=m.vars((2,),cost=[-3,-2],upper=1,integer=True)
        m.constraint([(x,1)],upper=1);m.mip_start=np.array([0.,1.])
        r,A=m.solve(0.,0.)
        checked_incumbent(m,r,A)
        self.assertTrue(r.warm_start_submitted)
        self.assertLessEqual(r.fun,-2.+1e-8)

    def test_infeasible_or_fractional_integer_start_rejected(self):
        for start in [np.array([1.,1.]),np.array([.5,.5]),np.array([np.nan,0.])]:
            m=Model('highs');x=m.vars((2,),cost=-1,upper=1,integer=True)
            m.constraint([(x,1)],upper=1);m.mip_start=start
            with self.assertRaises(ValueError):m.solve(1.,0.)

    def test_native_lower_bounds_are_enforced(self):
        m=Model('highs');x=m.vars((1,),cost=1,upper=2,integer=True)
        m.lower[0]=1.;m.constraint([(x,1)],upper=2)
        r,A=m.solve(1.,0.)
        checked_incumbent(m,r,A)
        self.assertEqual(r.x[0],1.)

    def test_service_start_is_feasible_and_refinement_cannot_worsen_it(self):
        n=two_channels()
        action=plan(n,State.initial(n),np.ones((1,2,1),int),service_control=control(),solver_backend='highs')
        validate_action(n,State.initial(n),action)
        self.assertEqual(action.shipments[0,0,1,0],1)
        self.assertTrue(action.diagnostics['service_warm_start_submitted'])
        self.assertLessEqual(action.diagnostics['planning_objective'],action.diagnostics['service_warm_start_economic_objective']+1e-7)
        self.assertAlmostEqual(action.diagnostics['service_primary_incumbent_deficit'],.7)

    def test_native_and_scipy_tiny_physical_optima_agree(self):
        n=tiny()
        for demand in [0,1,3,5]:
            a=plan(n,State.initial(n),np.full((1,1,1),demand),gap=0.)
            b=plan(n,State.initial(n),np.full((1,1,1),demand),gap=0.,solver_backend='highs')
            self.assertAlmostEqual(a.diagnostics['planning_objective'],b.diagnostics['planning_objective'],places=6)
            validate_action(n,State.initial(n),b)


if __name__=='__main__':unittest.main()
