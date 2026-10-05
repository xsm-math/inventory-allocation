# Rolling inventory and transportation model

## Network and event timing

Warehouses $w\in W$ supply channels $c\in C$ with products $p\in P$ through ground or express mode $m$. Decisions are reviewed daily. In each day: (1) receive previously scheduled shipments and supplier orders; (2) estimate demand from observations through yesterday; (3) commit new orders and warehouse dispatches; (4) receive zero-lead express dispatches; (5) observe demand, satisfy it from channel stock, and record lost sales and holding costs. Unfilled demand is lost rather than backlogged.

A ground dispatch arrives after an integer lane-specific delay $L_{wcm}\ge1$. Express arrives on the dispatch day. Supplier orders arrive after $L^q=2$ days. Pipelines store quantities by absolute arrival day. Current-day receipts are removed from the pipelines before the planning model is built. No within-day reallocation occurs after demand is revealed.

## Decisions and constraints

Over a forecast horizon $t=0,\ldots,H-1$, define integer supplier orders $q_{twp}$, integer dispatches $x_{twcmp}$, and binary dispatch activations $z_{twcm}$. Warehouse inventory $I^W$, channel inventory $I^C$, planned sales $y$, planned lost demand $u$, and service slack $e$ are nonnegative continuous variables. With integer controls and integer demand, a physically integral inventory/sales solution exists, although these auxiliary variables are not explicitly constrained to be integer.

Known pipeline arrivals are $a^W,a^C$. Initial stock supplies the preceding-period inventory term at $t=0$. Balances are

$$
I^W_{twp}=I^W_{t-1,wp}+a^W_{twp}+q_{t-L^q,wp}-\sum_{c,m}x_{twcmp},
$$

$$
I^C_{tcp}=I^C_{t-1,cp}+a^C_{tcp}+\sum_{w,m}x_{t-L_{wcm},wcmp}-y_{tcp},
\qquad y_{tcp}+u_{tcp}=\widehat d_{tcp}.
$$

Terms with negative dispatch/order times are excluded because their known arrivals are already in $a$. Let $v_p$ be product volume, $K_m$ lane capacity, $B_w$ warehouse throughput, $Q_p$ supplier capacity, $k_p$ unit acquisition cost, and $B^q$ the daily procurement budget. Shared constraints are

$$
\sum_pv_px_{twcmp}\le K_mz_{twcm},\qquad
\sum_{c,m,p}v_px_{twcmp}\le B_w,
$$

$$
\sum_wq_{twp}\le Q_p,\qquad
\sum_{w,p}k_pq_{twp}\le B^q.
$$

A soft forecast service target adds

$$
\sum_ty_{tcp}+e_{cp}\ge\rho\sum_t\widehat d_{tcp}.
$$

This penalized horizon target is not a guaranteed realized fill rate. Orders and dispatches that would arrive outside the planning horizon are prohibited. The horizon shrinks near the end of an episode. This convention introduces finite-horizon effects, assessed in the horizon ablation.

## Objective

The model minimizes procurement, variable freight, fixed dispatch charges, on-hand holding, lost-demand penalties, and service slack costs, less sales revenue and terminal inventory credit:

$$
\begin{aligned}
\min\quad &\sum_{t,w,p}k_pq_{twp}
+\sum_{t,w,c,m,p} f_{wcm}v_px_{twcmp}
+\sum_{t,w,c,m}F_mz_{twcm}\\
&+\sum_{t,w,p}h^W_pI^W_{twp}
+\sum_{t,c,p}\bigl(h^C_pI^C_{tcp}+\pi_{cp}u_{tcp}-r_{cp}y_{tcp}\bigr)
+\lambda\sum_{c,p}e_{cp}\\
&-\eta\sum_p k_p\left(\sum_wI^W_{H-1,wp}+\sum_cI^C_{H-1,cp}\right).
\end{aligned}
$$

The reference settings use $\rho=0.8$, $\lambda=8$, and $\eta=0.8$. Known pipeline quantities arriving after the horizon are excluded from the variable-dependent terminal objective; their salvage contribution would be constant. There are no holding charges on in-transit stock, no physical storage upper bounds, and no inter-warehouse transfers. Throughput and lane capacity, rather than warehouse storage volume, are constrained.

Only the first day's controls are executed. The next day, states and forecasts are updated and the MILP is rebuilt. This is deterministic forecast-based model predictive control, not a multistage stochastic or distributionally robust optimization model. Channel prices are constant within an episode; planned future decisions are provisional.

## Forecasts and buffering

For each channel/product pair, the forecast is a convex combination of the last seven days' mean (weight 0.65) and observations from the same weekday within the last 28 days (weight 0.35), rounded to a nonnegative integer. The buffered variant adds 0.4 times the standard deviation of the preceding 28 days. It is a simple uncertainty adjustment, without a calibrated probability guarantee.

The simulator exposes uncensored past demand, including lost demand, to all policies. Retail sales alone would not generally supply this information; deployment on sales records would require a demand-censoring model. No realized future demand enters `decide` or `plan`.

## Solver handling

The sparse formulation uses SciPy's `milp` interface to HiGHS. The benchmark sets a 2-second time limit and a 2% relative MIP gap. A status of zero means the configured solver termination criterion was satisfied, not necessarily a zero-gap optimum. Time-limited feasible incumbents are accepted only after checking bounds, integrality, matrix residuals, and first-day action constraints. If no acceptable incumbent exists, the controller records a fallback and uses the base-stock policy.

The MIP gap refers to the deterministic planning objective and does not bound realized simulation performance. Supplier restrictions observed today are assumed to persist throughout the provisional horizon; their actual future recovery is not disclosed.

## Accounting and conservation

Episode economic value is realized revenue minus procurement, freight, dispatch, holding, and shortage costs, minus the cost of initial inventory, plus an 80%-of-cost terminal credit on all remaining warehouse, channel, and pipeline units. This is a synthetic finite-horizon valuation, not accounting profit. The planning service-slack regularizer is not charged in the realized ledger; actual shortage penalties and fill rates are reported separately.

At every transition, for each product,

$$
\text{total stock}_{t+1}=\text{total stock}_{t}+\text{new orders}_{t}-\text{sold}_{t},
$$

where total stock includes in-transit quantities. Dispatch changes location but never creates or consumes product. Arrival schedules, inventory nonnegativity, shared budgets, handling limits, and lane capacities are validated on every executed action.


## Explicit safety-stock extension

The `mpc_safety` controller keeps point forecasts. For each node/product, one-step residuals $r_j=d_j-\widehat d_j$ use only history available before $j$, for at most the last 28 days, requiring at least seven prior observations. Set

$$SS_{cp}=\left\lceil\Phi^{-1}(0.9)s(r_{cp})\sqrt{L^q}\right\rceil.$$

Add nonnegative slack $b_{tcp}$ and constraints

$$I^C_{tcp}+b_{tcp}\ge a_t SS_{cp},\qquad a_t=\min\{1,(H-1-t)/L^q\}.$$

The objective adds $8\sum_{t,c,p}b_{tcp}$. This planning regularizer is excluded from realized accounting. The reserve is released near the horizon boundary; at a one-day horizon it vanishes. Service slack remains separate. Reserve slack preserves feasibility under scarcity.

This is a normal independent-error approximation with a supplier-lead protection scale, not a calibrated echelon safety-stock formula. Ground transport, serial dependence, forecast bias, and capacity delays are not captured. The 0.9 quantile is distinct from the 0.8 forecast-service target and realized fill rate. Sensitivity changes the forecast-service target, not the reserve quantile. Both parameters are fixed before the main experiment.
