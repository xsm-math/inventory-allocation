# Findings and interpretation

These observations refer to the committed synthetic experiment, not operational data.
All main-study numbers are recoverable from `results/network/aggregate.csv` and
`paired_comparisons.csv`. Sensitivity and forecast numbers come from `results/research`.

## Economic performance is not service dominance

Buffered MILP improves mean economic value over base stock by 2,512 CNY (3.06%)
under normal demand, 8,424 CNY (10.31%) under a surge, and 5,660 CNY (8.33%)
under a supply shock. Paired 95% interval half-widths are 966, 1,922, and 986 CNY.
All are conditional on the specified demand model and parameterization.

Normal-demand fill falls from 97.03% to 94.37%, while variable freight falls from
19,042 to 12,849 CNY. Under the supply shock, buffered MILP's worst-channel fill
is only 64.47%, versus 83.38% for the baseline. Lower transport spending and
economic prioritization can improve the aggregate objective while harming service.

Unbuffered MILP loses 4.16% of baseline value in the normal regime. This negative
result is retained: optimizing a point forecast does not resolve uncertainty.

## Explicit reserve is useful but not uniformly superior

Safety-stock MILP reaches normal fill of 94.72%, compared with 89.28% for the
point-forecast controller; economic value is 83,593 versus 78,749 CNY. Relative
to base stock, value rises 1.73% but service falls. The buffered controller earns
more value than the explicit reserve controller in all three reference regimes.
This comparison does not isolate one formula's causal effect: the policies use
different demand/regularization treatments with fixed, untuned parameters.

The explicit reserve improves supply-shock worst-channel fill to 69.82%, compared
with 64.47% for buffered MILP, but remains below the baseline's 83.38%. It therefore
offers a different trade-off, not a universal replacement.

## Sensitivity reveals which constraints matter

Sensitivity uses six separate seeds under normal demand. At 70% handling/lane
capacity, safety-stock MILP has value 82,731 CNY and fill 94.59%, compared with
72,077 CNY and 92.26% for base stock. At 130% capacity the value gap is only
1,880 CNY, and baseline service is higher. Resource scarcity changes the relative
benefit of coordinated transport decisions. These cells vary both handling and
lane capacity, so they cannot identify which individual bottleneck dominates.
The paired value-gain interval at 70% capacity is 10,654 ± 3,752 CNY; at reference
capacity it is 2,035 ± 2,332 CNY and includes zero. The six-seed sensitivity study
does not establish positive gains in every parameter setting.

Raising the forecast-service target from 0.60 to 0.95 raises safety-stock MILP fill
from 95.21% to 95.80% and worst-channel fill from 92.08% to 94.07%; mean value
falls from 83,731 to 83,284 CNY. This is a modest, non-monotone response across
the three grid points, consistent with a soft constraint rather than a guarantee.

Increasing the shortage-cost multiplier from 0.5 to 2 raises this policy's fill
from 94.76% to 95.95%. Holding-cost changes barely move its fill in this grid.
When cost parameters change, realized values are recomputed under those costs:
do not interpret lower value across settings as an isolated deterioration in
decision quality. Base-stock actions are cost-insensitive for these particular
holding/shortage changes; their accounting values still change.

## Forecast error is measurable and material

Normal-demand mean WAPE is 30.16% for the blended predictor, 31.23% for the
recent-mean comparator, and 39.46% for seasonal naive. Under the surge the blended
predictor's WAPE is 30.65% and signed bias is -11.15%, indicating delayed
adaptation. The recent mean has less surge bias (-7.12%) but slightly higher WAPE
(31.18%). Accuracy rankings depend on the metric; operational value also depends
on where errors occur and on capacity and economic asymmetry.

## Reliability and scope

The final main benchmark has 144 episodes with no fallback days and one time-limit
day; its feasible incumbent was validated before execution. The maximum recorded
planning gap is approximately 2%. The sensitivity benchmark records no fallback
or time-limit days. These outcomes do not remove the
need for fallback handling under larger or different instances.

The horizon ablation and first-day scaling results are preserved in separate CSVs;
the latter repeats identical synthetic instances and is not an industrial stress
test. Source/config checksums, version records, raw seed-level outcomes and generated
tables make the study auditable. Additional real data, independent validation,
stronger baselines, calibrated reserve periods and hard service constraints are
needed before making deployment claims.
