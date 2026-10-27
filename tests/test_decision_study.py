import copy
import json
import unittest

import numpy as np
import pandas as pd

from supplychain.decision_study import (ROOT, validate_protocol, freeze_choices,
    paired_robust_difference, failure_upper, assess_choices)


def protocol():
    return json.loads((ROOT/'configs/decision_study.json').read_text(encoding='utf-8'))


def cell(candidate,resource,regime,value,fill=.9,worst=.8,quality=1.):
    return dict(candidate=candidate,resource=resource,regime=regime,value=value,fill=fill,worst=worst,
        economic_certified_fraction=quality,primary_certified_fraction=1.,fallback_days=0)


class DecisionStudyTests(unittest.TestCase):
    def test_protocol_rejects_reused_paths(self):
        p=protocol();validate_protocol(p)
        p['validation_seeds'][0]=40001
        with self.assertRaises(ValueError):validate_protocol(p)

    def test_service_gate_rejects_more_valuable_infeasible_policy(self):
        p=protocol();p['mandates']=[p['mandates'][2]]
        c=pd.DataFrame([cell('stock','base',r,100) for r in p['regimes']]+
            [cell('economic_milp','base',r,200,fill=.84) for r in p['regimes']])
        d,_,_=freeze_choices(c,p)
        self.assertTrue(all(x['selected']['candidate']=='stock' for x in d))

    def test_minimum_regime_value_not_mean_value_determines_ranking(self):
        p=protocol()
        c=pd.DataFrame([cell('stock','base',r,v) for r,v in zip(p['regimes'],[100,100,100])]+
            [cell('economic_milp','base',r,v) for r,v in zip(p['regimes'],[500,500,50])])
        d,_,_=freeze_choices(c,p)
        self.assertTrue(all(x['selected']['candidate']=='stock' for x in d))

    def test_fee_switch_and_threshold_are_consistent(self):
        p=protocol();p['fees_per_day']=[0,100]
        c=pd.DataFrame([cell('stock','base',r,1000) for r in p['regimes']]+
            [cell('stock','budget_plus_10pct',r,3100) for r in p['regimes']])
        d,_,thresholds=freeze_choices(c,p)
        self.assertEqual(d[0]['selected']['resource'],'budget_plus_10pct')
        self.assertEqual(d[1]['selected']['resource'],'base')
        self.assertAlmostEqual(thresholds[0]['validation_switch_fee_per_day'],50.)

    def test_quality_gate_rejects_uncertified_milp(self):
        p=protocol()
        c=pd.DataFrame([cell('stock','base',r,100) for r in p['regimes']]+
            [cell('economic_milp','base',r,200,quality=.97) for r in p['regimes']])
        d,_,_=freeze_choices(c,p)
        self.assertEqual(d[0]['selected']['candidate'],'stock')

    def test_no_eligible_option_is_explicit(self):
        p=protocol()
        c=pd.DataFrame([cell('stock','base',r,100,fill=.7,worst=.5) for r in p['regimes']])
        d,_,_=freeze_choices(c,p)
        self.assertTrue(all(x['selected'] is None and x['status']=='no_supported_option' for x in d))

    def test_paired_bootstrap_keeps_common_seed_and_all_regimes(self):
        a=np.array([[100,10,50],[10,100,50],[40,40,50]],float)
        self.assertEqual(paired_robust_difference(a,a),(0.,0.,0.))
        mean,lo,hi=paired_robust_difference(a+7,a)
        np.testing.assert_allclose([mean,lo,hi],[7,7,7],atol=1e-12)

    def test_zero_failures_does_not_establish_ninety_percent_sla(self):
        self.assertGreater(failure_upper(0,12),.1)
        self.assertAlmostEqual(failure_upper(0,12),1-.05**(1/12))
        self.assertEqual(failure_upper(12,12),1.)

    def test_heldout_cannot_replace_frozen_choice(self):
        p=protocol();p['mandates']=p['mandates'][:1];p['fees_per_day']=[0]
        c=pd.DataFrame([cell('stock','base',r,100) for r in p['regimes']])
        decisions,_,_=freeze_choices(c,p)
        rows=[]
        for s in p['test_seeds']:
            for r in p['regimes']:
                for candidate,value,fill in [('stock',50,.7),('economic_milp',500,.95)]:
                    rows.append(dict(candidate=candidate,resource='base',regime=r,seed=s,economic_value=value,
                        fill_rate=fill,worst_channel_fill=fill,days=p['days'],economic_precision_unmet_days=0,
                        service_primary_precision_unmet_days=0,fallback_days=0,mean_solve_seconds=0))
        result=assess_choices(pd.DataFrame(rows),p,decisions).iloc[0]
        self.assertEqual(result.candidate,'stock')
        self.assertEqual(result.status,'test_service_not_confirmed')


if __name__=='__main__':unittest.main()
