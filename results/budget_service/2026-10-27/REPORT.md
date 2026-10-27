# Service priority and procurement budget

All demand and logistics economics are synthetic. Controls were fixed from the prior study; one service tolerance is selected globally on fresh validation paths.
Candidate counts and solver phases differ. Two-stage service priority uses half the per-decision solver limit for each phase; actual elapsed times are reported.

## Frozen service choice

```
{
  "candidate": "service-d0.02",
  "validation_eligible": false,
  "validation_min_fill": 0.7957016110990685,
  "validation_min_worst": 0.7705684200363672,
  "validation_max_deficit": 0.05429838890093153,
  "validation_mean_value": 162610.62083333332
}
```

## Held-out outcomes

```
         resource       regime        family  economic_value  fill_rate  worst_channel_fill  balanced_mean_pass  balanced_episode_violation_rate
             base       normal economic_milp     175826.8250   0.966562            0.943933                True                            0.000
             base       normal  service_milp     175572.7250   0.965828            0.945127                True                            0.000
             base       normal         stock     164926.4000   0.977093            0.960019                True                            0.000
             base supply_shock economic_milp     148638.7250   0.821593            0.645148               False                            1.000
             base supply_shock  service_milp     141426.8875   0.824532            0.801780               False                            1.000
             base supply_shock         stock     128075.9125   0.847271            0.785628               False                            0.500
             base        surge economic_milp     188130.2750   0.805273            0.627590               False                            1.000
             base        surge  service_milp     180065.4500   0.805223            0.777888               False                            1.000
             base        surge         stock     149659.5375   0.811758            0.740569               False                            1.000
budget_plus_10pct       normal economic_milp     176927.8625   0.971393            0.955095                True                            0.000
budget_plus_10pct       normal  service_milp     176902.1500   0.972143            0.957200                True                            0.000
budget_plus_10pct       normal         stock     163748.5750   0.988314            0.977392                True                            0.000
budget_plus_10pct supply_shock economic_milp     154577.9250   0.847082            0.685896               False                            1.000
budget_plus_10pct supply_shock  service_milp     148889.4000   0.847919            0.814845               False                            0.500
budget_plus_10pct supply_shock         stock     139689.3500   0.891731            0.850184                True                            0.000
budget_plus_10pct        surge economic_milp     198089.4625   0.839644            0.686527               False                            0.875
budget_plus_10pct        surge  service_milp     193117.7125   0.839672            0.808501               False                            0.375
budget_plus_10pct        surge         stock     174452.1625   0.877068            0.849619                True                            0.250
```

## Paired policy, budget and interaction effects

```
      regime                                        effect  economic_value_difference  fill_rate_difference  worst_channel_fill_difference
      normal                      service_minus_stock@base                 10646.3250             -0.011265                      -0.014892
      normal              service_minus_economic_milp@base                  -254.1000             -0.000734                       0.001194
      normal         service_minus_stock@budget_plus_10pct                 13153.5750             -0.016171                      -0.020192
      normal service_minus_economic_milp@budget_plus_10pct                   -25.7125              0.000750                       0.002105
      normal                        budget_increment@stock                 -1177.8250              0.011222                       0.017373
      normal                budget_increment@economic_milp                  1101.0375              0.004831                       0.011162
      normal                 budget_increment@service_milp                  1329.4250              0.006315                       0.012072
      normal                 budget_by_service_interaction                   228.3875              0.001484                       0.000911
       surge                      service_minus_stock@base                 30405.9125             -0.006535                       0.037320
       surge              service_minus_economic_milp@base                 -8064.8250             -0.000050                       0.150299
       surge         service_minus_stock@budget_plus_10pct                 18665.5500             -0.037396                      -0.041118
       surge service_minus_economic_milp@budget_plus_10pct                 -4971.7500              0.000028                       0.121974
       surge                        budget_increment@stock                 24792.6250              0.065310                       0.109050
       surge                budget_increment@economic_milp                  9959.1875              0.034371                       0.058938
       surge                 budget_increment@service_milp                 13052.2625              0.034449                       0.030613
       surge                 budget_by_service_interaction                  3093.0750              0.000078                      -0.028325
supply_shock                      service_minus_stock@base                 13350.9750             -0.022740                       0.016152
supply_shock              service_minus_economic_milp@base                 -7211.8375              0.002939                       0.156632
supply_shock         service_minus_stock@budget_plus_10pct                  9200.0500             -0.043812                      -0.035338
supply_shock service_minus_economic_milp@budget_plus_10pct                 -5688.5250              0.000837                       0.128950
supply_shock                        budget_increment@stock                 11613.4375              0.044460                       0.064555
supply_shock                budget_increment@economic_milp                  5939.2000              0.025489                       0.040747
supply_shock                 budget_increment@service_milp                  7462.5125              0.023388                       0.013065
supply_shock                 budget_by_service_interaction                  1523.3125             -0.002102                      -0.027682
```

All differences have unadjusted paired Student-t 95% intervals in paired_effects.csv; n=8 seeds per regime. Do not pool regimes as independent replicates.
Effects of budget compare unchanged policies on common demand paths. Interaction is the service-policy budget response minus the economic-MILP budget response.
Changing the budget cap is hypothetical; economic value includes actual procurement costs but no extra financing or facility-reservation fee.

## Optimistic ex-post resource bounds

```
         resource       regime  aggregate_fill_upper_bound  worst_channel_fill_upper_bound
             base       normal                    1.000000                        1.000000
             base supply_shock                    0.924767                        0.924767
             base        surge                    0.868024                        0.868024
budget_plus_10pct       normal                    1.000000                        1.000000
budget_plus_10pct supply_shock                    0.975775                        0.975775
budget_plus_10pct        surge                    0.916601                        0.916601
```

These bounds relax distribution timing and capacities. They see demand after choices are frozen and are never inputs to a controller. Passing a bound is not proof of service feasibility.
The service policy prioritizes forecast-conditioned cumulative channel service; it does not guarantee realized service. If primary optimality is unproven, the refinement cap uses its feasible incumbent, not the unknown optimum.
Primary service precision is 0.001 absolute deficit units (0.1 percentage point). The precision certificate and exact optimality are reported separately; solver success at this tolerance is not exact optimality.
The first service incumbent is retained if economic refinement has no valid solution; all such fallbacks are counted. If the primary phase fails, the existing feasible stock fallback applies.
Further limits: one network, small fixed synthetic samples, uncensored demand, finite horizon/salvage, tuned tolerance conditional on validation, no multiple-comparison correction or production evidence.
