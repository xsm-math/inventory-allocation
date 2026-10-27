# Validation-frozen service and economic study

This extension asks when rolling MILP improves economic value against tuned
heuristics without an unacceptable service deterioration. All demand and logistics
parameters remain synthetic. The study does not establish operational savings.

## Inputs and partitions

`configs/service_frontier.json` is the declared protocol. The reference network,
economic ledger and event sequence are retained. Episodes last 42 operating days
after 42 observed historical days. Each policy starts with identical inventory.
The existing initial inventory charge and 80% terminal salvage remain in the
ledger; finite-horizon sensitivity is not yet addressed by this extension.

Development seeds 101–112 and 201–206 identify paths already used by previous
studies. New validation seeds are 10001–10006; new test seeds are 20001–20012.
All three sets are disjoint. New paths are independent draws from the same known
synthetic generator, not a new empirical population or evidence of OOT validity.
Normal and supply-shock regimes deliberately share demand draws and must not be
pooled as independent replications.

The three regimes are normal, a 45% demand surge and a supplier/budget shock.
At 42 operating days, changes begin on day 14; the supply shock ends on day 28.
Controllers observe only history, stock/pipelines and the current supply factor.
No future demand, future recovery date or regime identity is supplied to them.

## Candidate families and tuning budget

Each family has nine candidates; CPU tuning budgets differ and are not equalized.

| Family | Candidate grid | Allocation rule |
|---|---|---|
| Coverage stock | Review days 1/2/4 × forecast buffer 0/0.4/0.8 historical standard deviations | Prioritize low inventory coverage; use express for current shortfall, ground for future coverage |
| Economic stock | Same review/buffer grid | Prioritize `(price - unit procurement cost + shortage penalty - cheapest mode freight) / product volume`; coverage breaks ties |
| Rolling MILP | Planning service slack penalty 0/8/32 × forecast buffer 0/0.4/0.8 | Existing sparse MILP, five-day horizon, two-second limit, 2% requested MIP gap |

For stock heuristics, local ground targets cover ground lead plus review days;
network procurement covers supplier lead plus maximum ground lead plus review
days. The legacy coverage-stock configuration (review=2, buffer=0) is retained
as a fixed control. Heuristics retain their natural coverage instead of being
artificially restricted to the MILP horizon. These are complete-policy comparisons,
not a solver-only causal experiment. No best-baseline claim beyond these grids is
made. The economic heuristic does not jointly optimize fixed dispatch batching.

Only forecast buffers, review coverage and planning regularization are tuned.
Realized procurement, transport, shortage, holding and revenue parameters are the
same for every candidate. Planning penalties never enter the realized ledger.

## Service profiles and selection

| Profile | Mean aggregate fill | Mean episode-worst-channel fill |
|---|---:|---:|
| relaxed | 0.80 | 0.60 |
| balanced | 0.85 | 0.75 |
| strict | 0.90 | 0.80 |

These are declared evaluation targets, not calibrated contractual commitments or
guarantees. A configuration is validation-eligible only if both means pass in
**every** declared regime. Each family/profile chooses one configuration globally
across regimes by largest equal-regime mean economic value. No oracle selects a
different policy after learning the test regime. Candidate ID breaks value ties.

If none is eligible, select the candidate minimizing the maximum positive
service deficit across the two metrics and regimes, then maximize mean economic
value, then candidate ID. Label it validation-infeasible; never silently weaken
targets. This is an evaluation fallback, separate from feasible-action fallback
when a solver provides no usable incumbent.

All choices are written to `selection.json` before test execution, together with
the protocol, candidate definitions and normalized source/network hashes. The
test stage rejects changed protocol/source/network and executes only the union
of frozen candidates. A candidate reused by several profiles is simulated once;
multiple profile rows are not independent episodes. Existing test data may be
reported again but cannot be overwritten by the test stage.

## Results and qualification

Every selected choice appears in the held-out summary, including service failures.
Report economic value, aggregate fill, episode-worst-channel fill, fraction of
episodes violating either target, shipping plus dispatch, holding, shortage costs,
fallback and time-limit days. Mean episode-worst-channel fill is not the same as
minimum fill across all channels and all episodes.

Economic and service differences use common demand paths and are paired by seed
within each regime. Student-t 95% intervals have 12 test seed-level observations.
No pooled cross-regime independence, multiple-comparison adjustment or statistical
power guarantee is claimed. They condition on the validation-selected choices.

A comparison against tuned coverage stock is marked `comparison_qualified` only
when both choices were validation-eligible, both test means satisfy that profile
in the reported regime, and paired lower 95% bounds for aggregate/worst-channel
service differences are at least -0.01/-0.03 respectively. These absolute fill
differences are predeclared diagnostic noninferiority margins. A positive economic
lower interval bound then receives the label `exploratory_positive`. Given multiple
profiles, regimes and metrics, this is exploratory evidence rather than a formal
confirmatory superiority claim. All unqualified gains remain visible.

The graph shows the entire validation grid and frozen test choices. It does not
interpolate unattained policies or claim exact risk/service matching. Gate and
episode violation details are in CSV, including channels hidden by aggregate fill.

## Reproduce

```bash
python -m pip install -r requirements-lock.txt
python -m unittest discover -s tests -v
python -m supplychain.frontier --stage validate --output results/service-frontier-new
python -m supplychain.frontier --stage test --output results/service-frontier-new
python -m supplychain.frontier --stage report --output results/service-frontier-new
```

`--stage run` executes these in order. Use a fresh run directory. The experiment
checks exact episode coverage, unique keys, paired demand hashes and realized
economic identities. Ordinary tests cover selection counterexamples, ineligible
choices, partition overlap, test-stage isolation, modified frozen inputs, service
loss despite higher profit, legacy compatibility, physical feasibility and
past-only tuned decisions. Published legacy reference tables are preserved.

Limitations: one network topology, uncensored synthetic demand, finite episode
and salvage assumptions, small validation/test samples, limited candidate grids,
unequal CPU tuning budgets, different natural planning horizons, mean-based service
targets and no multi-network, real-data or industrial-scale validation.

## Ex-post necessary resource bounds

After selection is frozen, `python scripts/capacity_bound.py --run-dir <run>`
diagnoses whether procurement resources alone rule out a service target on the
held-out demand paths. This is not supplied to any controller or used for tuning.

For realized product/channel demand totals D[c,p], relaxed sales Y[c,p], initial
stock I[p] and arriving purchases Q[p], the LP retains:

```text
0 <= Y[c,p] <= D[c,p]
sum_c Y[c,p] <= I[p] + Q[p]
0 <= Q[p] <= sum_{t: t + supplier_lead < days} floor(supply_factor[t] * capacity[p])
sum_p unit_cost[p] * Q[p] <= sum_{t: t + supplier_lead < days} supply_factor[t] * budget
sum_p Y[c,p] >= alpha * sum_p D[c,p], 0 <= alpha <= 1
```

Maximize total sales (aggregate fill bound) and alpha (worst-channel fill bound)
in separate LPs. Distribution timing, warehouse/lane capacities, daily resource
coupling and integer quantities are relaxed, making these optimistic upper bounds.
An empirical mean bound below the declared mean target certifies that no feasible
controller could attain that target on those same paths. Passing both separate
bounds is not a sufficient joint feasibility certificate. Budget/supplier +10%
experiments modify only these optimistic bounds, not actual simulated policies;
they are not estimates of realizable expansion value.

The diagnostic manifest records its script and frozen-selection hashes separately.
Tests cover a hand-computed budget example, orders arriving after the evaluation
end, zero demand, invalid input and realized feasible controllers below the bounds.

Generated reference artifacts under `results/service_frontier/` are stored verbatim
in Git so checkout does not alter their recorded byte hashes. Source hashes normalize
line endings. New runs on another operating system may serialize text differently;
exact cross-platform result-file hash equality is not required for numeric reproduction.
