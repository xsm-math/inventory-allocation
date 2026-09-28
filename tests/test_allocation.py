import itertools
import unittest
import numpy as np
import pandas as pd
from allocation import allocate, evaluate, run_case, STRATEGIES

class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame(dict(sku=['X']*3, channel=['A','B','C'], forecast=[2,3,2], capacity=[3,4,3], margin=[5,3,6], shipping=[1,1,2], holding=[1,2,1], shortage_penalty=[2,1,3]))
        self.demand = np.array([[0,2,1],[2,1,3],[3,4,0],[1,2,2]])
    def test_exact_against_enumeration(self):
        for stock in range(11):
            for floor in [0, .25]:
                lower = np.ceil(floor*self.rows.forecast).astype(int).to_numpy()
                if sum(lower)>stock:
                    continue
                x = allocate(self.rows, stock, self.demand, floor=floor)
                actual = evaluate(self.rows, x, self.demand)[0]['economic_value']
                oracle = max(evaluate(self.rows, np.array(y), self.demand)[0]['economic_value'] for y in itertools.product(*[range(l,c+1) for l,c in zip(lower,self.rows.capacity)]) if sum(y)<=stock)
                self.assertAlmostEqual(actual, oracle)
    def test_constraints_all_strategies(self):
        for stock in range(3,16):
            for strategy in STRATEGIES:
                x = allocate(self.rows, stock, self.demand, strategy, .25)
                self.assertLessEqual(x.sum(), stock)
                self.assertTrue((x <= self.rows.capacity).all())
                self.assertTrue((x >= 1).all())
    def test_infeasible_and_invalid(self):
        for stock in [0, -1, 2.5]:
            with self.assertRaises(ValueError):
                allocate(self.rows, stock, self.demand, floor=.25)
        with self.assertRaises(ValueError):
            allocate(self.rows, 5, [[-1, 2, 3]], floor=0)
    def test_zero_demand_keeps_stock(self):
        x = allocate(self.rows, 8, np.zeros((4,3)), floor=0)
        self.assertEqual(x.sum(), 0)
    def test_reproducible(self):
        self.assertEqual(run_case(self.rows,5), run_case(self.rows,5))

if __name__ == '__main__':
    unittest.main()
