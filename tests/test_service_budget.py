import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from supplychain.service_budget import (ROOT,validate_protocol,candidates,select_service,
    paired_effects,test_stage as execute_test_stage,write_json,write_csv,fingerprint,check_grid,load_frozen,file_hash)


def protocol():return json.loads((ROOT/'configs/service_budget.json').read_text())


class ServiceBudgetTests(unittest.TestCase):
    def test_fresh_paths_include_old_test_as_development_and_reject_reuse(self):
        p=validate_protocol(protocol())
        self.assertIn(20001,p['development_seeds'])
        p['test_seeds'][0]=20001
        with self.assertRaises(ValueError):validate_protocol(p)
        p=protocol();p['development_seeds'].remove(20001);p['test_seeds'][0]=20001
        with self.assertRaises(ValueError):validate_protocol(p)

    def test_controls_are_fixed_and_tolerance_selection_remains_global(self):
        specs=candidates(protocol())
        self.assertEqual(len(specs),5)
        self.assertEqual(specs[0]['options'],{'review_days':4,'forecast_buffer':0.})
        stats=pd.DataFrame([dict(candidate='high-profit',family='service_milp',mean_value=1000,min_fill=.8,min_worst=.6),
                            dict(candidate='service',family='service_milp',mean_value=700,min_fill=.9,min_worst=.85)])
        choice=select_service(stats,{'fill':.85,'worst':.75})
        self.assertEqual(choice['candidate'],'service')
        self.assertTrue(choice['validation_eligible'])
        self.assertEqual(choice,select_service(stats.iloc[::-1],{'fill':.85,'worst':.75}))

    def test_budget_effect_and_interaction_match_hand_calculation(self):
        p=protocol();p['regimes']=['normal']
        rows=[]
        for seed in [1,2,3]:
            for family,base,increment in [('stock',100.,10.),('economic_milp',120.,20.),('service_milp',90.,35.)]:
                for resource,added in [('base',0.),('budget_plus_10pct',increment)]:
                    rows.append(dict(seed=seed,regime='normal',family=family,resource=resource,
                                     demand_sha256=str(seed),economic_value=base+added,
                                     fill_rate=.8,worst_channel_fill=.7,procurement=50.))
        effects=paired_effects(pd.DataFrame(rows),p).set_index('effect')
        self.assertEqual(effects.loc['budget_increment@service_milp','economic_value_difference'],35.)
        self.assertEqual(effects.loc['budget_by_service_interaction','economic_value_difference'],15.)
        self.assertEqual(effects.loc['service_minus_economic_milp@base','economic_value_difference'],-30.)
        bad=pd.DataFrame(rows);bad.loc[0,'demand_sha256']='different'
        with self.assertRaises(ValueError):paired_effects(bad,p)

    def test_test_stage_uses_only_frozen_choice_and_detects_modified_evidence(self):
        p=protocol();specs=candidates(p);chosen=[specs[0],specs[1],specs[3]]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            write_json(out/'selection.json',{'protocol':p,'fingerprint':fingerprint(p),
                       'validation_files':{},'selected':chosen})
            for name in ['test_channels.csv','representative_daily.csv']:
                write_csv(pd.DataFrame({'x':[1]}),out/name)
            with patch('supplychain.service_budget.run_grid',return_value=(pd.DataFrame({'x':[1]}),0.)) as run:
                with patch('supplychain.service_budget.select_service',side_effect=AssertionError('test selection')):
                    write_csv(pd.DataFrame({'x':[1]}),out/'test_episodes.csv')
                    # The real stage rejects an existing test file. Remove this
                    # fixture first; have the mocked run write its own output.
                    (out/'test_episodes.csv').unlink()
                    def generate(*args):
                        write_csv(pd.DataFrame({'x':[1]}),out/'test_episodes.csv')
                        return pd.DataFrame({'x':[1]}),0.
                    run.side_effect=generate
                    execute_test_stage(p,out)
            self.assertEqual(run.call_args.args[1],chosen)
            self.assertEqual(run.call_args.args[2],p['test_seeds'])
            with self.assertRaises(FileExistsError):execute_test_stage(p,out)
            write_csv(pd.DataFrame({'x':[1]}),out/'validation.csv')
            frozen=json.loads((out/'selection.json').read_text())
            frozen['validation_files']={'validation.csv':file_hash(out/'validation.csv')}
            write_json(out/'selection.json',frozen)
            write_csv(pd.DataFrame({'x':[2]}),out/'validation.csv')
            with self.assertRaises(ValueError):load_frozen(p,out)

    def test_canonical_serialization_uses_lf_and_finite_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            write_json(p/'x.json',{'x':1})
            write_csv(pd.DataFrame({'x':[.12345678901234567]}),p/'x.csv')
            self.assertNotIn(b'\r\n',(p/'x.json').read_bytes())
            self.assertNotIn(b'\r\n',(p/'x.csv').read_bytes())
            with self.assertRaises(ValueError):write_json(p/'bad.json',{'x':float('nan')})


if __name__=='__main__':unittest.main()
