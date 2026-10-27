# Decision study: predeclared policy and budget choices

This study is specified before validation and held-out runs. All demand, prices,
service mandates and extra-budget facility fees are synthetic or hypothetical.
It asks which fixed controller/resource combination is supported by a stated
service mandate when future regime probabilities are unknown.

## Fixed design

- 42 operating days, five-day planning horizon; normal, surge and supply shock.
- Three controls fixed from earlier development: stock review 4 / buffer 0;
  economic MILP buffer .8 / service regularization 32; two-stage service MILP
  with those same settings, goal .90, deficit tolerance .02, precision .001.
- Base procurement cap and cap +10%. The cap is a constraint, not expenditure.
- Four seconds per daily MILP decision; service splits this into two seconds
  primary and two seconds economic refinement. Both MILPs use HiGHS 1.15.1,
  one thread and fixed random seed. Six independent episode workers share the
  machine. Time-limited incumbents can vary across hardware/load.
- Economic planning certificate: relative gap <=2% OR absolute gap <=25
  illustrative CNY. This is a practical planning precision, not exact optimality.
- Validation seeds 50001–50006; held-out seeds 60001–60012. Earlier inspected
  paths, including the seed-40005 runtime engineering probe, are development.
  No prior path enters these new partitions.
- 108 validation and 216 test policy episodes; common demand paths for all
  controls and resources. All daily diagnostics and channel records retained.

The native adapter passes a checked service incumbent to refinement and never
returns a worse economic objective than that start. Primary activation binaries
are fixed to one while their cost is zero; this does not restrict the projected
feasible shipment set. They are repaired to actual lane activation before the
economic stage. Independent small-instance tests verify integer optima, physical
feasibility, service deficit, incumbent preservation and solver agreement.

## Mandate first, robust value second

Mandates are illustrative decision inputs, not claimed business SLAs:

| Mandate | Mean aggregate fill | Mean worst-channel fill |
|---|---:|---:|
| Value led | .80 | .60 |
| Channel protection | .80 | .75 |
| Broad service | .85 | .75 |
| Strict | .90 | .80 |

An option must meet both mean service thresholds in **every validation regime**.
In each regime at least 98% of MILP days must meet the economic certificate;
at least 99% of primary service days must meet the .001 precision. No physical
or refinement fallback is allowed. Stock has no solver certificate to satisfy.

Among eligible options maximize the minimum regime mean economic ledger value
minus the extra-budget facility fee. This expresses aversion to unknown regime
probabilities; it is not a claim of equal probabilities or a distributionally
robust guarantee outside these three regimes. Ties prefer stock, economic MILP,
then service MILP; then base resource. Controllers never see a regime label.

The extra-budget fee grid is 0, 100, 250, 500 illustrative CNY per operating day.
The fee buys access to a larger cap for all 42 days. Actual procurement is already
charged in the ledger. The grid does not represent an observed lending rate.
Between the best eligible base and expanded-budget options the validation switch
fee is `(expanded robust value - base robust value) / 42`. No base eligible option
means no finite switch threshold within these candidates. No eligible option
means explicit refusal, not selection of a near miss.

Choices and runner-up options are frozen for each mandate/fee before test paths
are simulated. No regime-specific oracle and no replacement on held-out data.

## Held-out interpretation

Report service and solver-quality confirmation for each frozen choice, all
candidate means with unadjusted Student-t 95% intervals, and paired bootstrap
95% intervals for robust net-value difference versus the frozen runner-up.
Bootstrap jointly resamples seed rows across all regimes/options (2,000 draws,
fixed seed); it does not reselect. These intervals are conditional on validation
selection and this synthetic generator. Small samples and multiple reported
comparisons limit stronger claims.

Record episode service violations and one-sided exact binomial 95% upper bounds
on failure probability within each regime. Even zero failures in 12 paths gives
an upper failure probability around 22%; mean gates cannot certify a 90% SLA.

Ex-post resource bounds relax timing, lanes and warehouse handling and see realized demand.
An upper bound below a target excludes the target on those paths. An upper bound
above it cannot establish that any implementable controller can meet it.
Distinguish physical exclusion from inadequacy of the three tested candidates.

Reproduce with `python -m supplychain.decision_study --stage run --output
results/decision-study-new`. Stages `validate`, `test`, `report` also work
separately. Source, network, protocol, native version and evidence hashes are
checked; changes invalidate the frozen run. Legacy studies reproduce at their
recorded commits. This study does not show real business savings or deployment.

Then run `python scripts/decision_diagnostics.py --run-dir results/decision-study-new`
to add descriptive paired effects, figures and the report's constraint clarification.
The script refreshes the report manifest and records its own source hash. It does
not modify selection, validation, test or bound inputs. The physical model has no
storage-volume cap; the effective bound relaxation removes timing and transport /
handling restrictions.

## Additional resource diagnosis, added after validation froze

The postprocessor also solves an ex-post pooled LP minimizing a **common budget
cap multiplier** across the held-out paths in one regime. It retains initial
product totals, arriving supplier quantity totals and a pooled acquisition-cost
budget for each path. It removes logistics and per-day acquisition timing.
Average episode aggregate fill and average episode worst-channel fill must meet
the same mandate thresholds; it does not require each path to meet them.

Its optimum is a necessary budget multiplier for those empirical mean targets
in this relaxation. A required increase of x% is a lower bound on required
resources, not a sufficient investment plan. If even this LP is infeasible,
increasing only the budget cannot meet the relaxed target. This diagnostic was
added after validation selection and is never used to select or retune policies.
Analytic one-product tests check cost, initial stock, supplier infeasibility and
the difference between mean and per-episode service gates.
