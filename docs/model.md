# Model and algorithm

## Sample-average formulation

Consider $C$ channels and $N$ planning scenarios $d^{(1)},\ldots,d^{(N)}$. For a feasible integer allocation $x$, define

$$
f_i(x_i)=\frac1N\sum_{n=1}^{N}\left[m_i\min(d_i^{(n)},x_i)-s_ix_i-h_i(x_i-d_i^{(n)})^+-p_i(d_i^{(n)}-x_i)^+\right].
$$

The problem is to maximize $\sum_i f_i(x_i)$ subject to

$$
\ell_i\le x_i\le c_i,\qquad \sum_i x_i\le S,\qquad x_i\in\mathbb Z,\qquad
\ell_i=\lceil\alpha\widehat d_i\rceil.
$$

All cost and margin parameters are nonnegative. Feasibility requires $\ell_i\le c_i$ for every channel and $\sum_i\ell_i\le S$. The implementation rejects infeasible instances.

Shipping costs apply to every dispatched unit. Margin is revenue net of variable product cost on sold units; fixed procurement expenditure is excluded. Unsold channel units incur a period holding charge with no separate salvage proceeds. Undispatched central stock has zero modeled cost and no future value. Shortage penalties are preference parameters rather than accounting expenditures.

## Marginal value

Let $\widehat q_i(k)=N^{-1}\sum_n\mathbf1\{d_i^{(n)}\ge k\}$. Adding the $k$th unit either satisfies one unit of demand or remains unsold. Consequently,

$$
\Delta_i(k):=f_i(k)-f_i(k-1)
=(m_i+p_i)\widehat q_i(k)-h_i[1-\widehat q_i(k)]-s_i.
$$

Since $\widehat q_i(k)$ is nonincreasing, $\Delta_i(k)$ is nonincreasing. Each $f_i$ is therefore discretely concave. Correlation between channel demands does not affect this argument: the objective is additive and the inventory decision is made before demand is observed.

## Proposition

Starting from $x=\ell$, repeatedly assign a unit to a channel with the largest positive available $\Delta_i(x_i+1)$, provided $x_i<c_i$. Stop when the inventory budget is exhausted or no positive increment remains. The resulting allocation maximizes the sample-average objective.

**Proof.** Any feasible allocation extends $\ell$ by choosing a prefix from each sequence

$$
\Delta_i(\ell_i+1),\ldots,\Delta_i(c_i),
$$

with at most $R=S-\sum_i\ell_i$ increments overall. Each sequence is nonincreasing. The largest unselected increment in their union is always among the first unselected elements: later elements cannot exceed their predecessors. The algorithm therefore selects the globally largest positive increments in nonincreasing order, with predecessor-first tie breaking. Its selection is prefix-feasible and reaches the upper bound obtained by ignoring the prefix restriction and choosing at most $R$ increments from the union. Hence it is optimal. Zero-valued increments may be omitted without affecting the objective. $\square$

The result applies to a single shared unit-budget constraint and separable concave values. Fixed shipment charges, coupled service constraints, and nonuniform resource requirements generally invalidate this argument. The algorithm is an application of the marginal-allocation principle; no claim of algorithmic novelty is made.

## Implementation

A heap stores one available increment per channel. Tail probabilities are computed directly from the scenario array. For $U$ incremental allocations, runtime is $O((C+U)N+U\log C)$ including initialization, and memory is $O(NC+C)$. Precomputed empirical tails would reduce repeated scenario scans.

`tests/test_allocation.py` compares the optimizer against exhaustive enumeration on small instances and checks feasibility for each policy. These tests validate implementation behavior; optimality for the stated model follows from the proposition.
