# Ex-post optimistic purchasing-resource bounds

Realized demand is used after validation selection is frozen; it is never supplied to a policy.
Bounds relax network flow/timing and integer controls, retaining initial stock and arriving procurement quantity/budget.
Aggregate fill and worst-channel fill are maximized separately. Passing both separate bounds is not sufficient for joint feasibility.
A mean upper bound below a service target rules out that empirical mean target on these fixed demand paths even for a clairvoyant relaxed controller.
Capacity increases here are hypothetical and affect optimistic bounds only; they do not estimate achievable operational gains or investment value.

```
           scenario       regime  aggregate_fill_upper_bound  worst_channel_fill_upper_bound
               base       normal                    1.000000                        1.000000
               base supply_shock                    0.921640                        0.921640
               base        surge                    0.865042                        0.865042
  budget_plus_10pct       normal                    1.000000                        1.000000
  budget_plus_10pct supply_shock                    0.970755                        0.970755
  budget_plus_10pct        surge                    0.913454                        0.913454
supplier_plus_10pct       normal                    1.000000                        1.000000
supplier_plus_10pct supply_shock                    0.924764                        0.924764
supplier_plus_10pct        surge                    0.878685                        0.878685
```

```
 profile scenario       regime  aggregate_fill_upper_bound  worst_channel_fill_upper_bound  mean_target_ruled_out_by_bound
 relaxed     base       normal                    1.000000                        1.000000                           False
 relaxed     base supply_shock                    0.921640                        0.921640                           False
 relaxed     base        surge                    0.865042                        0.865042                           False
balanced     base       normal                    1.000000                        1.000000                           False
balanced     base supply_shock                    0.921640                        0.921640                           False
balanced     base        surge                    0.865042                        0.865042                           False
  strict     base       normal                    1.000000                        1.000000                           False
  strict     base supply_shock                    0.921640                        0.921640                           False
  strict     base        surge                    0.865042                        0.865042                            True
```
