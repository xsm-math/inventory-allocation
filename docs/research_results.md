# Executed research results

| Regime | Policy | Economic value (CNY) | Fill rate | Worst-channel fill |
|---|---|---:|---:|---:|
| normal | Base stock | 82,168 | 97.03% | 94.68% |
| normal | Rolling MILP | 78,749 | 89.28% | 86.10% |
| normal | Buffered MILP | 84,679 | 94.37% | 91.56% |
| normal | Safety-stock MILP | 83,593 | 94.72% | 90.97% |
| surge | Base stock | 81,722 | 83.57% | 78.85% |
| surge | Rolling MILP | 83,314 | 76.64% | 66.48% |
| surge | Buffered MILP | 90,146 | 79.78% | 65.11% |
| surge | Safety-stock MILP | 86,971 | 80.07% | 65.37% |
| supply_shock | Base stock | 67,956 | 88.09% | 83.38% |
| supply_shock | Rolling MILP | 68,597 | 78.28% | 63.08% |
| supply_shock | Buffered MILP | 73,615 | 82.04% | 64.47% |
| supply_shock | Safety-stock MILP | 70,714 | 82.26% | 69.82% |

| Regime | Policy vs. base stock | Paired gain (CNY) | 95% interval half-width | Relative gain |
|---|---|---:|---:|---:|
| normal | Rolling MILP | -3,418 | 912 | -4.16% |
| normal | Buffered MILP | 2,512 | 966 | 3.06% |
| normal | Safety-stock MILP | 1,425 | 860 | 1.73% |
| surge | Rolling MILP | 1,592 | 1,697 | 1.95% |
| surge | Buffered MILP | 8,424 | 1,922 | 10.31% |
| surge | Safety-stock MILP | 5,249 | 1,580 | 6.42% |
| supply_shock | Rolling MILP | 641 | 979 | 0.94% |
| supply_shock | Buffered MILP | 5,660 | 986 | 8.33% |
| supply_shock | Safety-stock MILP | 2,759 | 976 | 4.06% |

Main study: 144 episodes; 0 fallback days; 1 time-limit days; maximum recorded MIP gap 2.00%.

Paired, unadjusted Student-t intervals describe seed variation within the synthetic model. They do not establish real-world savings or guarantee service.

## One-factor sensitivity

Normal regime; seeds [201, 202, 203, 204, 205, 206]; 108 unique episodes. Reference cells are reused, not additional independent observations.

| Factor | Level | Policy | Economic value | Fill | Worst channel |
|---|---:|---|---:|---:|---:|
| capacity | 0.7 | Base stock | 72,077 | 92.26% | 89.46% |
| capacity | 0.7 | Safety-stock MILP | 82,731 | 94.59% | 91.37% |
| capacity | 1 | Base stock | 81,628 | 97.24% | 95.40% |
| capacity | 1 | Safety-stock MILP | 83,663 | 95.16% | 92.27% |
| capacity | 1.3 | Base stock | 81,937 | 97.63% | 95.83% |
| capacity | 1.3 | Safety-stock MILP | 83,816 | 95.33% | 92.80% |
| holding_cost | 0.5 | Base stock | 82,862 | 97.24% | 95.40% |
| holding_cost | 0.5 | Safety-stock MILP | 84,562 | 95.18% | 92.28% |
| holding_cost | 1 | Base stock | 81,628 | 97.24% | 95.40% |
| holding_cost | 1 | Safety-stock MILP | 83,663 | 95.16% | 92.27% |
| holding_cost | 2 | Base stock | 79,159 | 97.24% | 95.40% |
| holding_cost | 2 | Safety-stock MILP | 81,916 | 95.16% | 92.25% |
| service_target | 0.6 | Base stock | 81,628 | 97.24% | 95.40% |
| service_target | 0.6 | Safety-stock MILP | 83,731 | 95.21% | 92.08% |
| service_target | 0.8 | Base stock | 81,628 | 97.24% | 95.40% |
| service_target | 0.8 | Safety-stock MILP | 83,663 | 95.16% | 92.27% |
| service_target | 0.95 | Base stock | 81,628 | 97.24% | 95.40% |
| service_target | 0.95 | Safety-stock MILP | 83,284 | 95.80% | 94.07% |
| shortage_cost | 0.5 | Base stock | 82,049 | 97.24% | 95.40% |
| shortage_cost | 0.5 | Safety-stock MILP | 84,624 | 94.76% | 90.58% |
| shortage_cost | 1 | Base stock | 81,628 | 97.24% | 95.40% |
| shortage_cost | 1 | Safety-stock MILP | 83,663 | 95.16% | 92.27% |
| shortage_cost | 2 | Base stock | 80,786 | 97.24% | 95.40% |
| shortage_cost | 2 | Safety-stock MILP | 81,686 | 95.95% | 93.90% |

## Forecast evaluation

Rolling one-day predictions use only observations before each decision. WAPE is averaged across seed-level ratios.

| Regime | Method | Mean WAPE | Mean signed bias |
|---|---|---:|---:|
| normal | blended | 30.16% | 0.24% |
| normal | recent_mean | 31.23% | -0.51% |
| normal | seasonal_naive | 39.46% | -0.27% |
| supply_shock | blended | 30.16% | 0.24% |
| supply_shock | recent_mean | 31.23% | -0.51% |
| supply_shock | seasonal_naive | 39.46% | -0.27% |
| surge | blended | 30.65% | -11.15% |
| surge | recent_mean | 31.18% | -7.12% |
| surge | seasonal_naive | 39.81% | -11.90% |

## Interpretation boundaries

Service and safety-stock targets are soft planning constraints, not realized service guarantees. Capacity sensitivity changes warehouse handling and transport lane capacities together, leaving procurement unchanged. Economic values under changed costs use those changed costs, so cross-setting changes are not pure policy-efficiency effects. Compare policies within each setting.

Normal and supply-shock forecast scores match because their demand processes match. The blended predictor need not outperform the recent-mean comparator. No parameter was selected by maximizing these results.
