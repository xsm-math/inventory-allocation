"""Integer allocation with separable concave expected economic value."""
import heapq
import numpy as np
import pandas as pd

REQUIRED = ['sku', 'channel', 'forecast', 'capacity', 'margin', 'shipping', 'holding', 'shortage_penalty']

def validate(rows, stock, floor):
    if not 0 <= floor <= 1:
        raise ValueError('floor must be between 0 and 1')
    if isinstance(stock, bool) or int(stock) != stock or stock < 0:
        raise ValueError('stock must be a nonnegative integer')
    if rows.empty or any(c not in rows for c in REQUIRED):
        raise ValueError('Missing required columns or empty input')
    if rows.channel.duplicated().any() or rows.sku.nunique() != 1:
        raise ValueError('Use one SKU and unique channels per solve')
    v = rows[REQUIRED[2:]].to_numpy(float)
    if not np.isfinite(v).all() or (v < 0).any():
        raise ValueError('Numeric fields must be finite and nonnegative')
    if (rows.capacity % 1 != 0).any():
        raise ValueError('Capacity must be integer')
    lower = np.ceil(floor * rows.forecast.to_numpy()).astype(int)
    caps = rows.capacity.to_numpy(int)
    if (lower > caps).any() or lower.sum() > stock:
        raise ValueError('Minimum allocation is infeasible; increase inventory or reduce the floor')
    return lower, caps

def scenarios(rows, count=400, seed=42, demand_scale=1., uncertainty=.30):
    """Synthetic correlated demand, not a fitted business forecast."""
    if count < 1 or demand_scale < 0 or uncertainty < 0:
        raise ValueError('Invalid scenario settings')
    rng = np.random.default_rng(seed)
    common = rng.lognormal(-uncertainty**2 / 2, uncertainty, (count, 1))
    local = rng.lognormal(-uncertainty**2 / 2, uncertainty, (count, len(rows)))
    return rng.poisson(rows.forecast.to_numpy() * demand_scale * common * local)

def allocate(rows, stock, demand, strategy='optimized', floor=.25):
    lower, caps = validate(rows, stock, floor)
    demand = np.asarray(demand)
    if demand.ndim != 2 or demand.shape[1] != len(rows) or not len(demand) or not np.isfinite(demand).all() or (demand < 0).any() or (demand % 1 != 0).any():
        raise ValueError('Demand must be a nonempty nonnegative integer scenario matrix')
    x = lower.copy()
    remaining = int(stock - x.sum())
    if strategy == 'proportional':
        # Capped proportional water filling, then largest remainder rounding.
        weights = rows.forecast.to_numpy(float)
        target = x.astype(float)
        left = float(remaining)
        while left > 1e-8:
            active = (target < caps - 1e-8) & (weights > 0)
            if not active.any():
                break
            add = np.minimum(left * weights[active] / weights[active].sum(), caps[active] - target[active])
            target[active] += add
            left -= add.sum()
        x = np.floor(target + 1e-9).astype(int)
        extra = int(round(target.sum())) - x.sum()
        for i in sorted(range(len(x)), key=lambda i: (-(target[i]-x[i]), i)):
            if extra and x[i] < caps[i]:
                x[i] += 1
                extra -= 1
        return x
    if strategy == 'margin_first':
        for i in np.argsort(-(rows.margin - rows.shipping).to_numpy(), kind='stable'):
            add = min(remaining, int(caps[i] - x[i]))
            x[i] += add
            remaining -= add
        return x
    if strategy != 'optimized':
        raise ValueError('Unknown strategy')
    # The kth unit sells iff demand >= k. Marginal values decrease with k.
    m, s, h, p = [rows[c].to_numpy() for c in ['margin', 'shipping', 'holding', 'shortage_penalty']]
    def gain(i, k):
        prob = np.mean(demand[:, i] >= k)
        return float((m[i] + p[i] + h[i]) * prob - h[i] - s[i])
    heap = [(-gain(i, int(x[i]+1)), i) for i in range(len(x)) if x[i] < caps[i]]
    heapq.heapify(heap)
    while remaining and heap:
        negative_gain, i = heapq.heappop(heap)
        if negative_gain >= 0:
            break  # Excess inventory may stay at the central warehouse.
        x[i] += 1
        remaining -= 1
        if x[i] < caps[i]:
            heapq.heappush(heap, (-gain(i, int(x[i]+1)), i))
    return x

def evaluate(rows, allocation, demand):
    sold = np.minimum(demand, allocation)
    missed = demand - sold
    leftover = allocation - sold
    contribution = (sold * rows.margin.to_numpy() - allocation * rows.shipping.to_numpy() - leftover * rows.holding.to_numpy()).sum(axis=1)
    value = contribution - (missed * rows.shortage_penalty.to_numpy()).sum(axis=1)
    total = demand.sum()
    return {'economic_value': float(value.mean()), 'contribution': float(contribution.mean()),
            'fill_rate': float(sold.sum()/total) if total else 1.,
            'shortage_units': float(missed.sum(axis=1).mean()),
            'leftover_units': float(leftover.sum(axis=1).mean()),
            'value_p05': float(np.quantile(value, .05))}, value

STRATEGIES = ['proportional', 'margin_first', 'optimized']

def run_case(rows, stock, floor=.25, seed=42, scale=1., uncertainty=.30):
    train = scenarios(rows, 400, seed, uncertainty=uncertainty)
    test = scenarios(rows, 2000, seed + 10000, scale, uncertainty)
    metrics, allocations, samples = [], [], {}
    for name in STRATEGIES:
        x = allocate(rows, stock, train, name, floor)
        metric, values = evaluate(rows, x, test)
        metrics.append(dict(strategy=name, **metric, central_stock=int(stock-x.sum())))
        allocations.append(dict(strategy=name, **dict(zip(rows.channel, map(int, x)))))
        samples[name] = values
    delta = samples['optimized'] - samples['proportional']
    return {'metrics': metrics, 'allocations': allocations,
            'paired_gain': {'mean': float(delta.mean()), 'ci95_halfwidth': float(1.96*delta.std(ddof=1)/np.sqrt(len(delta)))}}
