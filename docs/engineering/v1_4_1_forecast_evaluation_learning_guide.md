# Forecast evaluation learning guide

A baseline is a simple reference forecast. Comparing against zero, recent observations and seasonal repeats shows whether a learned model adds value. A random split would put future observations into training, so DecisionOS uses training ending at an origin followed by a contiguous future window.

The runner uses a fixed-length sliding window. An expanding window instead retains all earlier observations. Both can be valid when implemented chronologically. Forecasts are produced recursively with existing DecisionOS functions so predicted values, not future actual values, feed subsequent lags.

For training values y, zero predicts 0, mean predicts mean(y), naive repeats the last value, moving average uses the last 28 observations, and seasonal naive repeats the last 7 or 28 observations for the whole horizon.

Croston smooths nonzero demand size z and interarrival interval p at each nonzero event: z ← z + α(y−z), p ← p + α(interval−p), forecast z/p. The first interval is the number of observations up to the first nonzero value. SBA multiplies by 1−α/2. TSB uses a smoothed occurrence probability q updated on every observation, q ← q + β(I[y>0]−q), and smooths z on nonzero events. Its forecast is qz. The initial q is the reciprocal of the first event position. These implementations use α=β=0.1. All-zero history yields zero. Croston and SBA remain flat through a run of zeros, whereas TSB's q decreases. They model associations in historical observations, not why demand occurs.

MAE is mean absolute error, RMSE is the square root of mean squared error, and WAPE is 100 × sum absolute error / sum absolute actual demand. A zero WAPE denominator is undefined. Signed bias here is mean(prediction−actual), so positive values indicate overprediction. RMSSE divides evaluation mean squared error by the mean squared first difference of a series' training history, then takes the square root. Insufficient or constant training history gives undefined RMSSE. This implementation retains leading zeros and is a scoped per-series measure, not official M5 WRMSSE.

Study `baselines.py`, `evaluation/metrics.py`, `evaluation/backtest.py`, the benchmark runner, then the experiment protocol. The existing production forecast uses 14 canonical columns and clips negative Random Forest predictions.

Interview question: Why calculate RMSSE scale from training only? Answer: future observations would leak information into the denominator and change model comparisons. Why sum errors before computing aggregate WAPE? Answer: averaging per-series percentages gives different weighting and cannot represent aggregate demand.

## Reading the stratified follow-up

Characterization is implemented in `src/decisionos/evaluation/characterize.py`. Daily CV uses population standard deviation divided by average demand. Positive-size CV² uses only positive observations. ADI uses the number of observed training days divided by positive days. Production segments and research classifications answer different questions and are recorded separately.

The cohort is selected from 360 catalog pairs using only the earliest training history. This design increases coverage of rare patterns, so its pooled result is a result for this selected cohort. The sample contains 60 pairs across 10 stores. Classification can change at each origin because each fold has a different training window.

The research forest uses the existing training function and its 100-tree default. The LightGBM challenger receives the same feature columns and uses 100 trees with a seed. Both generate recursive predictions and clip negative results. Other hyperparameters differ, so the comparison is a first challenger study rather than a tuned model contest.

For hierarchical evaluation, the code first sums forecasts and actuals at each date for the same included pairs. It then computes the metric from those aggregated values. Cancellation of positive and negative errors can lower aggregate WAPE compared with product-store WAPE. The sampled total must be labeled as such.

The model-level WAPE denominator is total observed demand in that specific group. Series with no evaluation demand yield undefined WAPE when scored alone. RMSSE divides each series' forecast MSE by its own training first-difference MSE. The mean RMSSE summary excludes undefined denominators and records their count. Do not interpret it as official weighted M5 WRMSSE.

Interview question: Why can a stratified sample produce a different ranking than uniform sampling? Answer: it changes the mix and weight of hard and rare histories. A meaningful population claim needs a sampling design and appropriate weighting. Why can aggregate WAPE improve while item accuracy stays weak? Answer: summing first allows overpredictions and underpredictions to cancel.
