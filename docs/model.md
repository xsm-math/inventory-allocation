# Model and algorithm

For one SKU, channel i receives integer allocation x_i. Central inventory is S; channel capacity is c_i; the minimum allocation is l_i = ceil(alpha * forecast_i). Constraints are l_i <= x_i <= c_i and sum(x_i) <= S. Minimum allocations refer to forecast quantities, not a probabilistic service guarantee.

For demand scenario d and allocation x:

- sold = min(d, x)
- shortage = max(d - x, 0)
- leftover = max(x - d, 0)
- contribution = margin * sold - shipping * x - holding * leftover
- economic value = contribution - penalty * shortage

Maximize total expected economic value, averaged over planning scenarios. Shipping is charged on every dispatched unit. Inventory retained at the central warehouse incurs zero modeled cost. Fixed procurement costs are excluded.

## Exact marginal allocation

Let q_i(k) be the empirical probability that demand at channel i is at least k. Adding its kth unit changes expected value by:

```
gain_i(k) = (margin_i + penalty_i + holding_i) * q_i(k)
            - holding_i - shipping_i
```

When the unit sells, it earns margin, avoids one shortage penalty, and incurs shipping. Otherwise it incurs holding and shipping. Because q_i(k) is nonincreasing and the coefficients are nonnegative, gains are nonincreasing in k. Thus every channel's value function is discretely concave.

Start from the required lower bounds. Every feasible extension selects a prefix of each channel's remaining marginal sequence. Repeatedly selecting the largest currently available gain selects the largest feasible marginal values globally: a later value in a channel cannot exceed an earlier one, so its predecessor cannot block a strictly better unselected choice. Exchange any differing unit of another feasible solution for a larger greedy-selected unit, preserving a prefix selection through ties; objective cannot decrease. This gives an optimal solution under the single shared unit-budget constraint. Stop at nonpositive gains because inventory need not all be dispatched. Ties may produce multiple optimal allocations.

The heap handles C channels and U allocated incremental units. The present transparent implementation computes each empirical tail probability directly over N scenarios, costing O(U*(N + log C)); memory is O(N*C + C). Sorting demand and precomputing tail probabilities would improve scale. The included cases are intentionally small.

This proof does not extend to fixed transport costs, coupled service constraints, multiple warehouses, or arbitrary shared resource coefficients.

## Evaluation

Plan using 400 demand scenarios; freeze allocations; evaluate using 2,000 independent scenarios. The demand multiplier in sensitivity tests modifies test demand only, so policy construction cannot use future demand shifts. Fill rate is total sold divided by total demand over all test scenarios, not the unweighted mean of per-scenario ratios.

Compute paired differences of scenario economic values between optimized and proportional policies. Report mean(delta) ± 1.96 * sample_std(delta) / sqrt(2000), an approximate normal interval for Monte Carlo uncertainty conditional on the chosen policy and generator. The fifth percentile is a descriptive downside statistic, not an optimized risk constraint.
