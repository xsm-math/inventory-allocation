# Descriptive accounting diagnostics

Ledger contributions are service-priority minus economic-MILP, signed as contributions to economic value. Procurement, freight, dispatch, holding and shortage costs enter with minus signs; terminal salvage enters positively.
Components are algebraic attribution on paired simulated paths, not independent causal effects or a minimum economic cost of fairness. The full identity is checked per seed.

```
         resource       regime  n  revenue_contribution  procurement_contribution  shipping_contribution  dispatch_contribution  holding_contribution  shortage_penalty_contribution  initial_inventory_charge_contribution  terminal_salvage_contribution  economic_value_difference     ci95_low    ci95_high  max_identity_error
             base       normal  8              -628.625                   377.500                 92.425                  -0.50               -6.1500                        -57.250                                    0.0                          -31.5                  -254.1000  -622.972554   114.772554        2.364686e-11
budget_plus_10pct       normal  8               185.000                   -56.875                -75.550                 -82.75                3.3375                         26.125                                    0.0                          -25.0                   -25.7125  -310.480747   259.055747        1.909939e-11
             base        surge  8             -6061.125                  -133.125               -218.075                -381.75              279.3750                       -835.125                                    0.0                         -715.0                 -8064.8250 -9937.988227 -6191.661773        1.818989e-11
budget_plus_10pct        surge  8             -3810.375                   -81.250                 31.050                -315.50              260.7000                       -415.875                                    0.0                         -640.5                 -4971.7500 -6385.721551 -3557.778449        2.455636e-11
             base supply_shock  8             -3834.250                  -855.625               -850.750                -971.25              181.1625                       -710.125                                    0.0                         -171.0                 -7211.8375 -9073.797306 -5349.877694        1.818989e-11
budget_plus_10pct supply_shock  8             -3372.250                  -467.500               -656.525                -747.75              101.6250                       -546.625                                    0.0                            0.5                 -5688.5250 -7044.062026 -4332.987974        1.909939e-11
```

Incremental budget value per operating day is a deterministic rescaling of the declared paired budget effect, after actual procurement costs. It excludes financing and facility fees.
A positive point estimate can be read as an illustrative break-even ceiling for an additional daily budget-facility fee under these assumptions. Unadjusted intervals crossing zero leave that benefit uncertain; negative values do not support paying a positive fee. No actual lending terms, risk-adjusted ROI or investment recommendation is inferred.

```
       family       regime  n  operating_days  additional_actual_procurement  incremental_value_per_operating_day  ci95_low_per_day  ci95_high_per_day
        stock       normal  8              42                       4491.875                           -28.043452       -106.882782          50.795877
economic_milp       normal  8              42                       2923.125                            26.215179        -19.849598          72.279955
 service_milp       normal  8              42                       3357.500                            31.652976         -3.781986          67.087938
        stock        surge  8              42                      32778.750                           590.300595        531.441523         649.159668
economic_milp        surge  8              42                      24716.250                           237.123512        201.404995         272.842029
 service_milp        surge  8              42                      24664.375                           310.768155        264.849651         356.686659
        stock supply_shock  8              42                      16835.000                           276.510417        234.373384         318.647450
economic_milp supply_shock  8              42                      12995.000                           141.409524         92.683879         190.135168
 service_milp supply_shock  8              42                      12606.875                           177.678869        106.192692         249.165046
```
