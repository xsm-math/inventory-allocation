# Inventory Allocation Lab

A reproducible operations-research project for allocating limited inventory across sales channels. Includes an exact integer optimizer for a separable single-period model, two rule-based baselines, independent scenario evaluation, and a local Chinese-language dashboard.

**Portfolio demonstration using synthetic data. Not a DJI project, production deployment, or evidence of realized business savings.** Built with AI assistance; users should understand and extend the implementation before describing personal contributions in an interview.

![Held-out comparison](results/comparison.svg)

## Run

Python 3.10+:

```bash
cd inventory-allocation
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python experiment.py
python -m unittest discover -s tests -v
python server.py
```

Open http://127.0.0.1:8000. The dashboard runs locally and needs no API key. Change stock, the minimum allocation fraction, and held-out demand level. An infeasible minimum allocation produces an error instead of silently violating constraints.

## Business question

Before demand is known, distribute central stock among five sales channels. Higher-margin channels can be attractive, but allocating too much to them can cause expensive unsold inventory while other channels lose sales. Reserve a minimum allocation for every channel, respect channel capacity, then choose the remaining quantities.

Two independent SKUs are included. Their inventory cannot be substituted. The example uses 620 Camera-A units and 780 Gimbal-B units, a 25% forecast-based minimum allocation, and monetary amounts in illustrative CNY.

## Methods

| Strategy | Rule |
|---|---|
| Proportional | Satisfy minimum allocations, distribute remaining units by forecast weights subject to capacity, and round by largest remainder. |
| Margin first | Satisfy minimum allocations, then fill channels in descending margin less shipping cost. |
| Optimized | Satisfy minimum allocations, then allocate units in descending expected marginal economic value; retain units centrally if no positive gain remains. |

All three obey the same physical constraints. The first two deliberately represent simple full-dispatch rules; the optimizer can retain excess stock. In the default comparison all three dispatch the entire stock, so the difference is allocation mix rather than retention.

The marginal-value algorithm is exact for the empirical scenario objective here, not a general solution to supply-chain optimization. [Model and proof](docs/model.md).

## Results

400 planning scenarios and 2,000 independently seeded test scenarios; each policy uses the same test demands. Planning seed 42, test seed 10042. The two SKUs reuse seeds and are reported separately; they are not independent replications to pool for inference.

| SKU | Strategy | Mean economic value | Demand fill rate | Unsold channel units |
|---|---|---:|---:|---:|
| Camera-A | Proportional | 208,584.89 | 64.04% | 29.31 |
| Camera-A | Margin first | 178,863.34 | 52.60% | 134.87 |
| Camera-A | Optimized | 213,496.89 | 63.08% | 38.19 |
| Gimbal-B | Proportional | 81,845.04 | 64.85% | 39.00 |
| Gimbal-B | Margin first | 69,849.27 | 53.51% | 168.60 |
| Gimbal-B | Optimized | 83,763.82 | 64.13% | 47.20 |

Against proportional allocation, optimized economic value rises by **2.35% for Camera-A** and **2.34% for Gimbal-B**. Paired mean gains have approximate 95% Monte Carlo intervals of 4,912 ± 493 and 1,919 ± 181 CNY, respectively. These intervals condition on the fixed planning sample and assumed demand model; they do not capture model error or variation from re-training.

**The optimizer increases value but slightly reduces unit fill rate and increases channel leftovers.** The objective rewards margin and shortage costs, not maximum total units served. A business requiring higher fill rates would need a different objective or explicit service constraints. Simple margin-first allocation performs poorly because it ignores saturation and demand uncertainty.

`results/sensitivity.csv` covers 24 SKU/stock/demand settings (72 policy rows). Stock ranges from 50% to 110% of total forecast and test demand from 70% to 130% of forecast. Test shifts are hidden from the planner. Inspect these results rather than generalizing the default outcome.

## Data and validation

- `data/channels.csv`: editable synthetic forecasts, channel capacities, unit margins, shipping and holding costs, and shortage penalties.
- Forecasts are supplied assumptions, not estimates fitted to historical sales. Demand is Poisson with shared and channel-specific lognormal multipliers.
- `tests/test_allocation.py`: exhaustive small-instance optimality oracle, feasibility across policies, infeasible requests, zero demand, and reproducibility.
- `results/metrics.csv`, `allocations.csv`, `paired_gain.json`: numerical evidence behind the report.
- `server.py` and `web/index.html`: local dashboard and JSON endpoint; no cloud deployment implied.

## Scope and limitations

Single warehouse, one period, integer units, per-channel linear economics, and independent inventory budgets for each SKU. No lead times, replenishment, transfers, returns, fixed shipping charges, cross-product substitution, or joint budget constraints. Central inventory has zero modeled holding cost and no modeled future value. Channel holding charges are period costs; no separate salvage proceeds are modeled. Product procurement is treated as sunk; margin means revenue net of variable product cost for units sold. Shortage penalties express an assumed business preference and are not accounting expenses.

Real adoption would require verified inventory and order data, censored-demand estimation, stakeholder-approved economics, service policies, and rolling backtests. Multi-warehouse shipping or shared budgets would generally require a different solver.

中文项目解读与面试准备：[项目说明](docs/interview_zh.md)。
