# Service priority × procurement budget protocol

The previous study found a service/economic trade-off and necessary procurement
limits. This follow-up changes the allocation objective and purchasing budget in
a full paired factorial experiment. The method is a standard two-stage
epsilon-constraint construction with observed cumulative service accounting;
no new optimization algorithm is claimed.

## Pre-decision service state and formulation

At the start of day t, D[c] and S[c] are cumulative observed demand and realized
sales in channel c during days 0,...,t-1. These exclude today's unobserved demand
and all future observations. The existing forecast and physical model provide
forecast-horizon sales y[h,c,p] and forecast demand d[h,c,p]. Define

```text
denominator[c] = D[c] + sum_{h,p} d[h,c,p]
u >= 0
S[c] + sum_{h,p} y[h,c,p] + u * denominator[c] >= goal * denominator[c]
0 <= u <= goal
```

The first solve minimizes u, the largest positive projected channel fill shortfall
relative to `goal=0.90`. The second solve minimizes the original economic planning
objective with `u <= first_feasible_incumbent_u + tolerance`, capped at goal.
Historical unmet demand is a service deficit, not physical backorders: the simulator
still uses lost sales and never creates deliveries for already lost demand.

Both stages share all existing inventory, budget, supplier, lane, throughput,
integrality and lead-time constraints. Existing planning service regularization
and the forecast buffer are retained in the economic objective. Service accounting
is channel-level across products; it is not SKU-level fairness or a chance constraint.

The requested two-second solver limit is split into one second per phase. The
first phase requests zero relative MIP gap; the second uses the existing 2% gap.
Actual wall times include model assembly and are reported separately. A timed-out
primary with a checked feasible incumbent may be used, but its service optimum is
unproven and the cap is relative to that incumbent, not an unknown optimum. Primary
and secondary solver statuses, primary bound, projected fill and refinement fallback
are recorded. No feasible primary triggers the existing physical stock fallback.
If economic refinement has no valid incumbent, retain and revalidate the first
service incumbent against the added cap; count this fallback and leave its economic
MIP gap unknown. A timeout in either phase counts as a time-limit day.

Forecast-based projected service can differ from realized service. The goal and
tolerance do not guarantee service to every channel, episode or future population.

## Fixed controls and fresh partitions

The protocol is declared in `configs/service_budget.json` before new validation.
All prior inspected paths, including previous test seeds 20001–20012, are now
development data. New validation paths use 30001–30004; new test paths use
40001–40008. The implementation rejects overlap with any earlier partition even
if the development list is edited. New draws still use the same known synthetic
generator and network, so they provide no external or real-data validation.

Operating episodes last 42 days after 42 historical observations; the horizon is
five days for both MILP controls. Supply restrictions and demand regimes follow
the original event sequence. Controllers see today's supply factor but not the
regime label, future demand or disruption duration.

Fixed controls, chosen from the prior development study, are coverage stock
(review=4, buffer=0) and economic MILP (buffer=0.8, planning service penalty=32).
The service MILP uses the same buffer, horizon and regularization as economic MILP,
with service goal 0.90. Only tolerance 0/0.02/0.05 is selected in new validation.
Controls are not retuned. Candidate counts and solver-phase counts therefore
differ; no equal tuning-budget claim is made.

## Resource factorial and selection

Each policy is evaluated with the current procurement budget and a 10% larger
budget. Supplier quantities, warehouse/lane capacities, demand, costs and initial
inventory are unchanged. Supply shocks apply the same current-day 0.45 factor to
both budget variants. Policies do not receive advance recovery information.

Three service tolerances and two controls × two budgets × three regimes × four
validation seeds give 120 policy episodes. Select one tolerance globally across
all budget/regime cells; no per-regime or per-budget oracle switches it later.
Validation eligibility requires mean aggregate fill >=0.85 and mean episode-worst-
channel fill >=0.75 in every cell. If eligible candidates exist, maximize equal-cell
mean economic value; otherwise minimize the maximum positive service deficit,
then maximize value. Candidate ID breaks ties. All ineligibility remains visible.

Freeze the selected service configuration and both controls before testing. Three
policies × two budgets × three regimes × eight test seeds give 144 policy episodes.
All cells retain common demand hashes. Paired differences use eight seed-level
observations within each regime. Normal/supply-shock demand draws are shared and
regimes must not be pooled as independent observations.

## Outcomes and attribution

Report economic value, aggregate fill, episode-worst-channel fill, actual procurement
spend, mean and episode-level target violations, solve times, primary optimality
status and fallbacks. Report full channel summaries and first-seed daily diagnostics.
Service profiles 0.80/0.60, 0.85/0.75 and 0.90/0.80 are reported descriptively;
they do not select new policies from test results.

The paired effect table includes:

- Service minus stock and service minus economic MILP within each budget.
- Budget increment for each fixed policy.
- Interaction: `(service_budget10 - service_base) - (economic_budget10 - economic_base)`.

Each metric gets an unadjusted paired Student-t 95% interval. These exploratory
comparisons are conditional on the fixed/selected policies; no multiple-comparison
correction, retraining uncertainty or formal superiority claim is intended.
Policy effects include objective, historical-state and finite-solver-budget effects.
If a primary optimum is unproven or refinement falls back, an observed economic
loss cannot be interpreted as the minimum unavoidable economic cost of fairness.

Economic value includes additional actual procurement costs under the larger cap.
It excludes extra financing, credit-line fees or reservation charges for acquiring
that cap, which are not available. A positive budget effect within the simulator
does not establish actual expansion ROI. Policy and budget effects are isolated
within the declared simulated design; they do not establish external causality.

Optimistic resource bounds are recomputed after freezing on each test path and
checked above realized service. They relax distribution/timing/integrality and
are never controller inputs or evidence that an attainable policy exists.

## Reproduce and evidence

```bash
python -m pip install -r requirements-lock.txt
python -m unittest discover -s tests -v
python -m supplychain.service_budget --stage validate --output results/service-budget-new
python -m supplychain.service_budget --stage test --output results/service-budget-new
python -m supplychain.service_budget --stage report --output results/service-budget-new
```

`--stage run` performs the three stages in order. Tabular, JSON and report outputs
use canonical LF text and 17 significant digits for CSV numbers. JSON is finite;
generated figures are stored verbatim. Frozen input/source hashes,
validation-file hashes, test-file hashes and selection hash are checked. Reusing
an existing test directory is refused. Source edits during either experiment stage
invalidate it. Reproduce the earlier frozen service-frontier report from its source
snapshot at commit `6b214e8`; its historical evidence remains unchanged here.

Tests cover an independent two-channel one-unit allocation oracle, service/economic
tolerance trade-offs, cumulative-prefix causality, unavailable resources, invalid
histories, failure of either solver phase, hidden primary timeouts, fresh partitions,
frozen test-stage execution, altered evidence, factorial hand calculations and
canonical serialization.

Remaining limitations include one topology, a small sample, uncensored synthetic
demand, heuristic forecast buffering, finite episodes/salvage, continuous auxiliary
sales/inventory variables, no real procurement/transport calibration, and no
industrial-scale or production evidence.
