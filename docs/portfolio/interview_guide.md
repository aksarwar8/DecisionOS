# Interview guide

**Why use rolling-origin evaluation?** A forecast must use only data available at its origin. DecisionOS tests historical origins in time order and recursively feeds predictions into later lag features. This is more realistic than a random train/test split.

**Why retain simple baselines?** A complex model must improve on practical alternatives. In the 30-pair holdout, LightGBM L1 had lower pair-level WAPE than TSB, but greater sampled-aggregate underprediction. That trade-off prevented an automatic production replacement.

**Why is WAPE alone insufficient?** It pools absolute errors divided by total actual demand. It hides the direction of errors; signed bias, RMSE, per-series RMSSE and aggregate evaluation offer different perspectives. Small denominators and zero actual totals need special handling.

**How is leakage avoided?** Historical splits, feature construction and demand segmentation use data available at the forecast origin; recursive steps use earlier predictions rather than future actuals. Known future covariates need separate availability assumptions.

**How are decisions explained?** The recommendation combines forecast lead-time demand and user-specified safety stock with simulated inventory position, then applies minimum-order and order-multiple rules. The API returns the inputs, calculations and limitations. A budget allocation uses a heuristic, not a proven optimum.

**What is not production ready?** The inventory values are simulated; prediction intervals have limited validation; local snapshots are the default; PostgreSQL operational migrations and containers remain unverified; and public authentication and durable execution need more work. The currently served alias is not automatically promoted.
