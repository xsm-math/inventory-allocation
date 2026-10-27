# Validation-frozen inventory service study

Synthetic demand and illustrative CNY economics. No operational savings are established.

27 validation candidates; 6 validation and 12 test seeds per regime; 42 operating days.
Three families have equal candidate counts, not equal CPU tuning budgets. One global configuration per family/profile is selected across all validation regimes.
Each baseline keeps its natural protection coverage. This compares complete policies, not a solver-only causal effect.

Service gates apply to mean aggregate fill and mean episode-worst-channel fill in every validation regime. They do not guarantee every episode/channel or a future service probability.
Ineligible choices use an explicitly labeled minimum-service-deficit fallback. Test violations are never removed or used to choose replacements.

## Frozen choices

```
 profile            family            candidate  validation_feasible  validation_min_fill  validation_min_worst  validation_mean_value  validation_max_service_deficit
 relaxed    coverage_stock coverage_stock-r4-b0                False             0.799638              0.724782          147564.683333                        0.000362
 relaxed    economic_stock economic_stock-r4-b0                False             0.799535              0.556773          151249.977778                        0.043227
 relaxed              milp        milp-s32-b0.8                False             0.794116              0.616130          172326.061111                        0.005884
balanced    coverage_stock coverage_stock-r4-b0                False             0.799638              0.724782          147564.683333                        0.050362
balanced    economic_stock economic_stock-r4-b0                False             0.799535              0.556773          151249.977778                        0.193227
balanced              milp          milp-s32-b0                False             0.752891              0.616813          154952.561111                        0.133187
  strict    coverage_stock coverage_stock-r4-b0                False             0.799638              0.724782          147564.683333                        0.100362
  strict    economic_stock economic_stock-r4-b0                False             0.799535              0.556773          151249.977778                        0.243227
  strict              milp          milp-s32-b0                False             0.752891              0.616813          154952.561111                        0.183187
 relaxed legacy_base_stock coverage_stock-r2-b0                False             0.781960              0.695211          141864.850000                        0.018040
balanced legacy_base_stock coverage_stock-r2-b0                False             0.781960              0.695211          141864.850000                        0.068040
  strict legacy_base_stock coverage_stock-r2-b0                False             0.781960              0.695211          141864.850000                        0.118040
```

## All held-out test results

```
 profile            family       regime  economic_value  fill_rate  worst_channel_fill  episode_service_violation_rate  test_mean_service_pass
 relaxed    coverage_stock       normal   164543.533333   0.981313            0.971988                        0.000000                    True
 relaxed    coverage_stock        surge   147655.100000   0.806872            0.724878                        0.416667                    True
 relaxed    coverage_stock supply_shock   127106.391667   0.850221            0.801698                        0.000000                    True
 relaxed    economic_stock       normal   160088.758333   0.972749            0.911525                        0.000000                    True
 relaxed    economic_stock        surge   160422.141667   0.806291            0.577911                        0.583333                   False
 relaxed    economic_stock supply_shock   132451.141667   0.851495            0.714317                        0.000000                    True
 relaxed              milp       normal   175092.341667   0.964146            0.942077                        0.000000                    True
 relaxed              milp        surge   184964.783333   0.790086            0.608885                        0.500000                   False
 relaxed              milp supply_shock   147207.825000   0.815612            0.641245                        0.333333                    True
balanced    coverage_stock       normal   164543.533333   0.981313            0.971988                        0.000000                    True
balanced    coverage_stock        surge   147655.100000   0.806872            0.724878                        1.000000                   False
balanced    coverage_stock supply_shock   127106.391667   0.850221            0.801698                        0.416667                    True
balanced    economic_stock       normal   160088.758333   0.972749            0.911525                        0.000000                    True
balanced    economic_stock        surge   160422.141667   0.806291            0.577911                        1.000000                   False
balanced    economic_stock supply_shock   132451.141667   0.851495            0.714317                        0.750000                   False
balanced              milp       normal   155427.741667   0.883637            0.864067                        0.000000                    True
balanced              milp        surge   166223.566667   0.748940            0.617976                        1.000000                   False
balanced              milp supply_shock   131068.741667   0.758702            0.613551                        1.000000                   False
  strict    coverage_stock       normal   164543.533333   0.981313            0.971988                        0.000000                    True
  strict    coverage_stock        surge   147655.100000   0.806872            0.724878                        1.000000                   False
  strict    coverage_stock supply_shock   127106.391667   0.850221            0.801698                        1.000000                   False
  strict    economic_stock       normal   160088.758333   0.972749            0.911525                        0.000000                    True
  strict    economic_stock        surge   160422.141667   0.806291            0.577911                        1.000000                   False
  strict    economic_stock supply_shock   132451.141667   0.851495            0.714317                        1.000000                   False
  strict              milp       normal   155427.741667   0.883637            0.864067                        1.000000                   False
  strict              milp        surge   166223.566667   0.748940            0.617976                        1.000000                   False
  strict              milp supply_shock   131068.741667   0.758702            0.613551                        1.000000                   False
 relaxed legacy_base_stock       normal   161741.850000   0.962962            0.944326                        0.000000                    True
 relaxed legacy_base_stock        surge   138133.500000   0.781137            0.686630                        0.750000                   False
 relaxed legacy_base_stock supply_shock   118771.666667   0.817170            0.743515                        0.416667                    True
balanced legacy_base_stock       normal   161741.850000   0.962962            0.944326                        0.000000                    True
balanced legacy_base_stock        surge   138133.500000   0.781137            0.686630                        1.000000                   False
balanced legacy_base_stock supply_shock   118771.666667   0.817170            0.743515                        0.916667                   False
  strict legacy_base_stock       normal   161741.850000   0.962962            0.944326                        0.000000                    True
  strict legacy_base_stock        surge   138133.500000   0.781137            0.686630                        1.000000                   False
  strict legacy_base_stock supply_shock   118771.666667   0.817170            0.743515                        1.000000                   False
```

## Paired comparisons against tuned coverage stock

```
 profile            family       regime  economic_value_difference  economic_value_ci95_low  economic_value_ci95_high  comparison_qualified                    status
 relaxed    economic_stock       normal               -4454.775000             -5397.509572              -3512.040428                 False service_condition_not_met
 relaxed    economic_stock        surge               12767.041667              9589.177737              15944.905596                 False service_condition_not_met
 relaxed    economic_stock supply_shock                5344.750000              3457.976334               7231.523666                 False service_condition_not_met
 relaxed              milp       normal               10548.808333              8754.789124              12342.827543                 False service_condition_not_met
 relaxed              milp        surge               37309.683333             31895.518719              42723.847947                 False service_condition_not_met
 relaxed              milp supply_shock               20101.433333             16918.120914              23284.745753                 False service_condition_not_met
 relaxed legacy_base_stock       normal               -2801.683333             -4195.791516              -1407.575150                 False service_condition_not_met
 relaxed legacy_base_stock        surge               -9521.600000            -11772.797942              -7270.402058                 False service_condition_not_met
 relaxed legacy_base_stock supply_shock               -8334.725000            -10054.217831              -6615.232169                 False service_condition_not_met
balanced    economic_stock       normal               -4454.775000             -5397.509572              -3512.040428                 False service_condition_not_met
balanced    economic_stock        surge               12767.041667              9589.177737              15944.905596                 False service_condition_not_met
balanced    economic_stock supply_shock                5344.750000              3457.976334               7231.523666                 False service_condition_not_met
balanced              milp       normal               -9115.791667            -11440.512839              -6791.070495                 False service_condition_not_met
balanced              milp        surge               18568.466667             13022.073205              24114.860128                 False service_condition_not_met
balanced              milp supply_shock                3962.350000               323.211006               7601.488994                 False service_condition_not_met
balanced legacy_base_stock       normal               -2801.683333             -4195.791516              -1407.575150                 False service_condition_not_met
balanced legacy_base_stock        surge               -9521.600000            -11772.797942              -7270.402058                 False service_condition_not_met
balanced legacy_base_stock supply_shock               -8334.725000            -10054.217831              -6615.232169                 False service_condition_not_met
  strict    economic_stock       normal               -4454.775000             -5397.509572              -3512.040428                 False service_condition_not_met
  strict    economic_stock        surge               12767.041667              9589.177737              15944.905596                 False service_condition_not_met
  strict    economic_stock supply_shock                5344.750000              3457.976334               7231.523666                 False service_condition_not_met
  strict              milp       normal               -9115.791667            -11440.512839              -6791.070495                 False service_condition_not_met
  strict              milp        surge               18568.466667             13022.073205              24114.860128                 False service_condition_not_met
  strict              milp supply_shock                3962.350000               323.211006               7601.488994                 False service_condition_not_met
  strict legacy_base_stock       normal               -2801.683333             -4195.791516              -1407.575150                 False service_condition_not_met
  strict legacy_base_stock        surge               -9521.600000            -11772.797942              -7270.402058                 False service_condition_not_met
  strict legacy_base_stock supply_shock               -8334.725000            -10054.217831              -6615.232169                 False service_condition_not_met
```

A comparison is qualified only if both choices met validation targets, both test means meet the declared profile in that regime, and paired 95% lower bounds for service differences exceed the predeclared noninferiority margins.
The positive label additionally requires a positive lower bound for economic value. These are exploratory, unadjusted intervals across multiple comparisons; they are not confirmatory superiority tests.

Full service-difference intervals and diagnostics are retained in CSV. Episode accounting includes procurement, freight, dispatch, holding, shortage penalties, initial inventory charge and terminal salvage.
Limits: one synthetic network; known uncensored demand; fixed five-day MILP horizon; finite 42-day experiment and salvage assumption; no independent real-world calibration.

## Reproduce

```bash
python -m pip install -r requirements-lock.txt
python -m unittest discover -s tests -v
python -m supplychain.frontier --stage run --output results/service-frontier-new
```
Separate validate/test/report stages are supported. Use a fresh run directory to preserve evidence.
