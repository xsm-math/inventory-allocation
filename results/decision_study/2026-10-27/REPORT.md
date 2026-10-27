# Frozen decision study

Synthetic one-network study. Mandates and extra-budget facility fees are hypothetical inputs. Controllers never receive the realized regime label.
Select once on validation: service and solver-quality gates in every regime; then maximize the minimum regime mean economic value less the facility fee. No held-out reselection.
Fee is per operating day for access to the extra budget cap, not an extra procurement charge. Actual procurement is already charged in the ledger.

## Frozen choices evaluated on held-out paths

```
           mandate  fee_per_day              status     candidate          resource test_mean_service_pass test_solver_quality_pass  test_min_fill  test_min_worst  test_net_worst_regime_value runner_up_candidate runner_up_resource  robust_value_difference  robust_difference_ci95_low  robust_difference_ci95_high
         value_led            0 test_mean_supported economic_milp budget_plus_10pct                   True                     True       0.830661        0.664499                154644.875000        service_milp  budget_plus_10pct              4733.358333                 4135.700208                  5319.464583
         value_led          100 test_mean_supported economic_milp budget_plus_10pct                   True                     True       0.830661        0.664499                150444.875000        service_milp  budget_plus_10pct              4733.358333                 4135.700208                  5319.464583
         value_led          250 test_mean_supported economic_milp budget_plus_10pct                   True                     True       0.830661        0.664499                144144.875000        service_milp  budget_plus_10pct              4733.358333                 4135.700208                  5319.464583
         value_led          500 test_mean_supported economic_milp budget_plus_10pct                   True                     True       0.830661        0.664499                133644.875000        service_milp  budget_plus_10pct              4733.358333                 4135.700208                  5319.464583
channel_protection            0 test_mean_supported  service_milp budget_plus_10pct                   True                     True       0.829599        0.800614                149911.516667               stock  budget_plus_10pct             11468.191667                10314.374792                 12755.593125
channel_protection          100 test_mean_supported  service_milp budget_plus_10pct                   True                     True       0.829599        0.800614                145711.516667               stock  budget_plus_10pct             11468.191667                10314.374792                 12755.593125
channel_protection          250 test_mean_supported  service_milp budget_plus_10pct                   True                     True       0.829599        0.800614                139411.516667               stock  budget_plus_10pct             11468.191667                10314.374792                 12755.593125
channel_protection          500 test_mean_supported  service_milp budget_plus_10pct                   True                     True       0.829599        0.800614                128911.516667               stock  budget_plus_10pct             11468.191667                10314.374792                 12755.593125
     broad_service            0 test_mean_supported         stock budget_plus_10pct                   True                     True       0.871104        0.836441                138443.325000                 NaN                NaN                      NaN                         NaN                          NaN
     broad_service          100 test_mean_supported         stock budget_plus_10pct                   True                     True       0.871104        0.836441                134243.325000                 NaN                NaN                      NaN                         NaN                          NaN
     broad_service          250 test_mean_supported         stock budget_plus_10pct                   True                     True       0.871104        0.836441                127943.325000                 NaN                NaN                      NaN                         NaN                          NaN
     broad_service          500 test_mean_supported         stock budget_plus_10pct                   True                     True       0.871104        0.836441                117443.325000                 NaN                NaN                      NaN                         NaN                          NaN
            strict            0 no_supported_option           NaN               NaN                    NaN                      NaN            NaN             NaN                          NaN                 NaN                NaN                      NaN                         NaN                          NaN
            strict          100 no_supported_option           NaN               NaN                    NaN                      NaN            NaN             NaN                          NaN                 NaN                NaN                      NaN                         NaN                          NaN
            strict          250 no_supported_option           NaN               NaN                    NaN                      NaN            NaN             NaN                          NaN                 NaN                NaN                      NaN                         NaN                          NaN
            strict          500 no_supported_option           NaN               NaN                    NaN                      NaN            NaN             NaN                          NaN                 NaN                NaN                      NaN                         NaN                          NaN
```

## Policy/resource held-out means

```
    candidate          resource       regime  economic_value  fill_rate  worst_channel_fill  economic_precision_unmet_days
economic_milp              base       normal   177502.783333   0.970494            0.946247                              0
economic_milp              base supply_shock   149030.733333   0.816257            0.636527                              0
economic_milp              base        surge   187118.633333   0.797490            0.617531                              0
economic_milp budget_plus_10pct       normal   179241.100000   0.979334            0.968891                              0
economic_milp budget_plus_10pct supply_shock   154644.875000   0.838429            0.664499                              0
economic_milp budget_plus_10pct        surge   197099.850000   0.830661            0.672782                              0
 service_milp              base       normal   177613.041667   0.970636            0.947473                              0
 service_milp              base supply_shock   142954.150000   0.817346            0.790349                              4
 service_milp              base        surge   179560.950000   0.797879            0.772056                              2
 service_milp budget_plus_10pct       normal   179495.458333   0.979585            0.967494                              0
 service_milp budget_plus_10pct supply_shock   149911.516667   0.840341            0.811737                              2
 service_milp budget_plus_10pct        surge   192485.666667   0.829599            0.800614                              1
        stock              base       normal   165360.600000   0.977654            0.964992                              0
        stock              base supply_shock   127139.275000   0.842811            0.782067                              0
        stock              base        surge   148320.916667   0.807378            0.735808                              0
        stock budget_plus_10pct       normal   165219.383333   0.991694            0.982922                              0
        stock budget_plus_10pct supply_shock   138443.325000   0.886606            0.846731                              0
        stock budget_plus_10pct        surge   172329.775000   0.871104            0.836441                              0
```

## Optimistic ex-post resource bounds

```
         resource       regime  mean_fill_upper  max_fill_upper  mean_worst_upper
             base       normal         1.000000        1.000000          1.000000
             base supply_shock         0.922561        0.954176          0.922561
             base        surge         0.865449        0.898957          0.865449
budget_plus_10pct       normal         1.000000        1.000000          1.000000
budget_plus_10pct supply_shock         0.972634        1.000000          0.972634
budget_plus_10pct        surge         0.913881        0.949264          0.913881
```

Bounds use future demand only for diagnosis and relax timing/lane/warehouse-handling restrictions. An upper bound below a target excludes that target on those paths; exceeding the target does not establish feasibility.
Per-metric mean Student-t intervals are unadjusted. Paired bootstrap intervals compare the robust scores of the frozen selected and runner-up options, resampling seed rows jointly across regimes; no option reselection. They are conditional on validation choices and the synthetic generator.
Mean service gates are not hard episode guarantees. Exact one-sided binomial bounds in test_summary.csv expose the limited evidence for episode reliability.
MILP economic certificates concern each forecast planning problem only: relative gap <=2% OR absolute gap <=25 illustrative CNY. Service primary precision is 0.001 deficit units. These do not certify realized policy optimality.
All daily diagnostics and channel records are retained. Wall-clock time limits can change incumbents on other hardware; source, versions, common demand hashes and numerical invariants are recorded.

The physical model has no storage-volume cap. Figures and paired descriptive effects are generated by scripts/decision_diagnostics.py; they do not alter frozen decisions.
