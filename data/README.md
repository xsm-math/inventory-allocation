# Data provenance

All network data are synthetic. `configs/network.json` defines three warehouses,
five retail channels (store groups), two SKUs, route lead times and illustrative
CNY costs. Channels are aggregate demand nodes rather than individually calibrated stores.

`supplychain.forecast.synthetic_history` generates 42 training days and 21 evaluation
days from a weekly Poisson-lognormal mixture. The main study uses seeds 101–112;
the sensitivity study uses 201–206. Policies receive only demand observed before
the current decision. The seed, generator source hash, configuration hash and demand
checksums identify the data used in each run. No customer or proprietary data are used.

Demand is regenerated instead of storing redundant draws. Export a seed's complete
forecast/actual and decision arrays using `python -m supplychain --policy mpc_safety`.
`channels.csv` belongs to the preserved single-period companion study.
