# Network experiment protocol

## Design

The reference network has three warehouses, five channels, two products, and two transport modes. All parameters are in `configs/network.json`. A 42-day synthetic history initializes forecasts; each subsequent 21-day episode uses fresh demand and starts from the same physical stock. Initial stock is priced at acquisition cost in the episode objective, and terminal stock, including pipeline quantities, receives an 80% credit. There is no steady-state warm-up exclusion: these are finite-horizon episodes.

Demand is a Poisson mixture with a common daily lognormal factor (log standard deviation 0.18), independent channel/product factors (0.12), and a weekly multiplier `[0.92, 0.96, 1.00, 1.02, 1.12, 1.20, 0.78]`. Both lognormal factors have mean one. Only history is supplied to each policy.

| Regime | Realized change | Controller information |
|---|---|---|
| Normal | No structural change. | Past uncensored demand and current stock/pipelines. |
| Demand surge | Demand intensity increases 45% from day 7 onward. | No advance announcement; forecasts adapt after observation. |
| Supply shock | Supplier quantity limits and procurement budget fall to 45% on days 7–13. | Today's restriction is known; its remaining duration is not. |

For episode lengths other than 21, change dates use integer thirds of the episode length. The demand generator uses seeds 101–112. Each seed/regime pair is evaluated under all four policies, yielding 144 episodes. Demand checksums verify common realizations within each comparison. Normal and supply-shock runs intentionally share demand draws; regimes are not pooled as independent observations.

## Policies

- **Base stock:** cover immediate forecast shortfalls using express, then replenish channels by ground. Order toward an aggregate network base-stock level covering supplier lead time, maximum ground lead, and two review periods (six days in this configuration). Procurement is allocated by geographical demand affinity, with budget scaling and integer rounding. This is a specified heuristic, not an optimized or universally optimal baseline.
- **Rolling MILP:** five-day lookahead, point forecasts, shared replenishment and transport constraints, fixed dispatch charges, and a soft forecast service target.
- **Buffered MILP:** identical to Rolling MILP except that forecasts are increased by 0.4 historical standard deviations.
- **Safety-stock MILP:** point forecasts with a separate soft inventory reserve estimated from past-only forecast residuals: quantile 0.9, two-day protection scale, slack penalty 8 CNY/unit/day, and a target tapering to zero at the horizon boundary.

The six-day baseline coverage and five-day MILP horizon are policy-specific parameters. The comparison is of complete policies rather than an isolated solver effect. Buffer and service weights are fixed for this experiment; no independent hyperparameter selection exercise is included.

## Estimation

For every regime/policy, arithmetic means and 95% Student-t intervals are computed across 12 independent seed-level episodes. Economic-value differences are paired by seed. Relative gain is the paired mean difference divided by the baseline mean, not the average of seed-level percentage changes. Reported intervals are unadjusted for multiple comparisons and conditional on the synthetic configuration.

Fill rate is total sold units divided by total demand within each episode, then averaged across episodes. Worst-channel fill is the minimum aggregate channel fill rate within an episode. Forecast WAPE is measured on unbuffered one-day forecasts for all policies; it is a common demand-forecast diagnostic, not the optimized buffered planning target.

## Additional studies

`horizon_ablation.csv` compares 3-, 5-, and 7-day MILP horizons using four matched seeds under normal and supply-shock regimes. The reference horizon's rows are reused from the main benchmark. Only the unbuffered controller is included. Longer horizons affect both planning and which replenishments can arrive before the model boundary.

`scaling.csv` solves synthetic first-day models at 2/4, 3/5, 5/10, and 8/20 warehouse/channel dimensions, using two products and 3/5/7/7-day horizons. Existing channel and warehouse parameter patterns are repeated; supplier capacity and budget are scaled with channel count. Three timing repeats use identical inputs and are not independent difficulty instances. The solve limit is 3 seconds and the requested relative MIP gap is 2%. These are small synthetic scaling checks, not industrial performance claims. Recorded time includes Python model construction and the solve.

## Reproduction and outputs

```bash
python -m supplychain.benchmark --seeds 12 --days 21 --time-limit 2
python -m supplychain.scaling
python -m supplychain --policy mpc_buffered --regime supply_shock --seed 101 --days 21
```

`episodes.csv` retains all episode summaries and demand hashes; `aggregate.csv` and `paired_comparisons.csv` contain the reported estimates. `representative_daily.csv` and `representative_channels.csv` retain seed-101 traces. `report.json` supplies the local interface. The single-episode CLI exports full order and shipment arrays; full action traces for all 144 episodes are regenerated rather than checked in. Package versions, random seeds, parameters, and the configuration hash are recorded in `metadata.json`.

Solver versions, floating-point behavior, and time limits can affect selected incumbents. Exact numerical equality across platforms is not guaranteed. Runtimes are environment-specific. The committed results record actual gaps and fallbacks, not merely the requested solver settings.

## Parameter sensitivity and forecast validation

`python -m supplychain.research` runs seeds 201–206 under normal demand, comparing base stock and safety-stock MILP. Service target levels are 0.60/0.80/0.95; shortage and holding cost multipliers are 0.5/1/2; handling and lane capacity multipliers are 0.7/1/1.3 (rounded down). Only one factor changes at a time. Procurement limits do not change in the capacity experiment. Four reference cells reuse the same simulations: 144 table rows represent 108 unique episodes. Scores under changed costs use changed accounting, so interpret policy differences within each setting.

The forecast study uses seeds 101–112, all three regimes, and expanding observed history. It compares the blended predictor against the rounded seven-day mean and seasonal naive. WAPE and signed bias are seed-level ratios averaged over seeds. Supply shocks do not alter demand, so normal and supply-shock forecast scores coincide. No model selection is performed.

`python scripts/reproduce.py` executes all studies and updates generated tables. `results/research/manifest.json` contains source checksums; `requirements-lock.txt` records tested versions. Findings are in `docs/research_results.md` and `docs/findings.md`.
