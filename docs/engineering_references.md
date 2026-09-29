# Engineering references

The following public projects informed the formulation and software structure. The new modules are an independent implementation; no source files were copied, and these projects are not runtime dependencies except for SciPy/HiGHS.

| Reference | Relevant design | Application in this repository |
|---|---|---|
| [Stockpyl](https://github.com/LarrySnyder/stockpyl) and its [simulation documentation](https://stockpyl.readthedocs.io/en/latest/tutorial/tutorial_sim.html) | Separate network state, inventory policies, event sequences, pipelines, and simulation output. | Explicit physical state and arrival schedules, interchangeable policies, and daily ledgers. Our decisions precede current demand; event ordering differs from Stockpyl's documented default. |
| [COIN-OR PuLP transportation case](https://coin-or.github.io/pulp/CaseStudies/a_transportation_problem.html) | Warehouse-to-customer flows constrained by supply and demand. | Warehouse/channel/mode/product flow variables with joint throughput limits. |
| [COIN-OR PuLP two-stage planning case](https://coin-or.github.io/pulp/CaseStudies/a_two_stage_production_planning_problem.html) | Distinguishing pre-observation decisions from decisions after uncertainty is revealed. | Explicit information boundary between planning and realized demand; the implemented controller is deterministic rolling planning, not a copy of the two-stage stochastic model. |
| [SciPy `milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) and [HiGHS](https://highs.dev/) | Sparse mixed-integer optimization, incumbent status, time limits, and relative optimality gaps. | Sparse constraint assembly, integer controls, binary fixed-charge activations, incumbent validation, and fallback diagnostics. |

The study combines established modeling components. It does not claim a new optimization algorithm, parity with the referenced packages, or empirical validation on an operating supply chain.
