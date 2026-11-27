# DecisionOS portfolio summary

DecisionOS explores a retail planning problem: historical demand is uneven, forecasts are uncertain, and inventory decisions require assumptions that the M5 dataset does not provide. The application combines a historical PostgreSQL dataset, Python forecasting and evaluation, MLflow, FastAPI and a React analytics interface.

The research compares statistical, intermittent-demand and machine-learning methods using chronological origins and a separate small holdout. On the 30-pair, one-origin holdout, LightGBM L1 had 68.08% pair-level WAPE but underpredicted the sampled aggregate; TSB had 69.71% pair-level WAPE and lower sampled-total WAPE. This illustrates why a single metric does not establish a production winner. See the [research report](../research/v1_4_3_optimization_report.md).

The application also presents interpretable anomaly signals and a simulated inventory decision workflow. Stock, lead times and costs are assumptions, not Walmart records. A historical replay compares inventory policies using observed sales as a demand proxy; it does not demonstrate actual savings. See the [prescriptive evaluation](../research/prescriptive_intelligence_evaluation.md).

Supported resume points, subject to your own involvement:

- Built a retail analytics application using PostgreSQL, FastAPI and React with bounded product-store forecasting and simulated replenishment decisions.
- Evaluated statistical and machine-learning forecasts using chronological backtests, a disjoint 30-pair holdout, and both pair-level and sampled-aggregate metrics.
- Implemented explainable inventory scenarios and compared policies in a historical replay with explicitly simulated costs and stock assumptions.

These statements do not claim a deployed production system or population-wide M5 accuracy.
