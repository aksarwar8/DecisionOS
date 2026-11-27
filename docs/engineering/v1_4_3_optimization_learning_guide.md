# V1.4.3 optimization learning guide

The research runner compares fixed grids on chronological folds. The statistical grid tests TSB and SBA smoothing from 0.05 to 0.3 and moving averages of 7–90 days. Model objectives include squared error, absolute error, Poisson and Tweedie. They reward different error behavior; a smaller WAPE does not guarantee low aggregate bias.

A hurdle model estimates probability of nonzero demand and conditional positive quantity separately, then multiplies the two. `HurdleModel` handles all-zero training data explicitly. Its recursive point forecast is still fed back into the existing canonical features.

The direct model in `direct_training` builds origin snapshots and 28 target leads that all fall inside the training window. The lead number is included as a feature. `direct_forecast` uses a single snapshot per pair and predicts all leads without feedback. It is a pooled direct model, with one model across lead values. Its calendar features describe the snapshot, not future calendar dates.

The adaptive rule classifies each pair from its own training history and routes intermittent, lumpy, zero and insufficient-positive histories to TSB, with the 28-day moving average for smooth and erratic histories. This is a predeclared heuristic, not a fitted per-series selector.

The development lock is created by `lock_candidates` before holdout evaluation. A separate seeded cohort and a later time window test the fixed methods. WAPE is pooled from underlying errors. RMSSE is calculated per series using training-only first differences; undefined scales are counted. Hierarchical scores aggregate aligned predictions and actuals before applying metrics.

Study `optimization.py`, its tests, the optimization runner, lock script, then the protocol and report. The holdout results are a single small sample. Pair-level WAPE favored LightGBM L1 while its negative bias worsened the sampled-total result, so this study does not justify replacing the operational model.

Interview question: Why is model selection performed before a holdout? Looking at the holdout while choosing the model makes it a development set. Why can direct and recursive models differ? Recursive models feed predictions back into lag features, while a direct model predicts leads from origin information. Neither method is guaranteed to win.
