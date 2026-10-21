# Technical audit — 2026-10-21

Status: reproducible synthetic research prototype. Full source review, executable regressions and complete experiments were performed; this is not evidence of operational savings.

## Scope and baseline

Baseline `1d1c649`. Reviewed the single-period allocator and the network state, forecasting, policies, sparse MILP, simulation, benchmarks and research/scaling workflows. The prior 20 tests passed, but did not cover the counterexamples below. The updated suite passes 26 tests on Python 3.14.7 and 26 on Python 3.12.14.

## Findings and repairs

| Finding | Evidence before repair | Repair / regression |
|---|---|---|
| Invalid supply bypassed capacity checks | With NaN supply factor an order of 999 passed a capacity-4 validation | Reject nonfinite/out-of-range supply at the common action boundary |
| Valid incumbent could crash diagnostics | A feasible result with `mip_gap=None` raised TypeError | Keep unknown gap null, retain feasibility checks, count observed gaps |
| Reserve configuration was partly unchecked | Nonfinite/negative optional reserve penalties reached model assembly | Validate optional safety quantile and penalty |
| Routine reproduction overwrote evidence | Original script regenerated committed results and README | Default isolated `results/reproduced`, `--output` on experiment commands, no README rewrite |
| Baseline comparison confounded lookahead | Legacy base-stock coverage differs from the five-day MILP horizon | Add explicit baseline-horizon option and 36 matched-path baseline episodes |

The updated tests also inject a corrupt incumbent and verify feasible fallback. An independent three-period physical enumeration checks the optimal objective and first action with procurement/transport queues, fixed dispatch costs and terminal service penalties; it does not reuse the MILP matrix or simulator transition. Bounds, integer controls, inventory conservation, one-day event order and past-only decisions remain covered. A zero/unknown gap must never be interpreted as realized stochastic optimality.

## Experiments actually rerun

Both archived baseline and repaired source completed the full workflow: 144 primary episodes; horizon ablation with 16 additional runs plus eight reused primary cells; 108 unique sensitivity episodes; forecast diagnostics; four scale instances with three solver repetitions each. An additional 36 baseline episodes use the same five-day lookahead and identical demand hashes. Cost reconciliation maximum absolute error: 2.91e-11 CNY.

Maximum primary economic-value difference from committed reference: 0 CNY. Solve durations are machine dependent and are not equality criteria.

Buffered MILP comparisons (mean paired difference / baseline mean value):

| regime | baseline | relative_gain | baseline_fill_rate | policy_fill_rate |
| --- | --- | --- | --- | --- |
| normal | legacy | 3.06% | 97.03% | 94.37% |
| normal | matched_horizon | 7.29% | 94.52% | 94.37% |
| surge | legacy | 10.31% | 83.57% | 79.78% |
| surge | matched_horizon | 20.08% | 80.11% | 79.78% |
| supply_shock | legacy | 8.33% | 88.09% | 82.04% |
| supply_shock | matched_horizon | 18.10% | 83.71% | 82.04% |

Matching lookahead changes the comparison; it does not establish solver-only causality or make the legacy baseline illegitimate. Both protocols are retained. Higher economic value can coincide with lower service. Intervals are seed-paired t intervals with n=12 per regime, without multiple-comparison correction.

## Reproduce

```bash
python -m pip install -r requirements-lock.txt
python scripts/reproduce.py
python scripts/audit.py
```

Use Python 3.14 for the recorded lock file; Python 3.12 compatibility uses `requirements.txt`. Choose a fresh output with `--output` when keeping several runs. The audit verifies source/config hashes, unique episode keys, common demand paths and realized ledger identities before adding the matched baseline. `run_manifest.json` records commands, environment and result hashes. The manual `Full inventory technical audit` workflow uploads synthetic results.

## Evidence and limits

[Audit checks](../results/audit/2026-10-21/audit.json) · [Matched comparisons](../results/audit/2026-10-21/matched_comparisons.csv) · [Verification](../results/audit/2026-10-21/verification.json).

Demand is synthetic and uncensored, economics illustrative, and the model deterministic receding-horizon MILP. No empirical calibration, calibrated chance constraints, hard realized service guarantee, storage-capacity constraint, transfers, multistage stochastic program or business deployment is claimed. Repeated scale solves are not independent business networks. Real data, independent baseline tuning and longer-horizon service studies remain required.
