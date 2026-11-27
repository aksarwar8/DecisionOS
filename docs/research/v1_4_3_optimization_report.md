# V1.4.3 optimization and adaptive forecasting report

## Evidence and setup

The development set is the existing 60-pair cohort at the three 2015 origins. A fixed statistical grid, five LightGBM configurations, a two-stage hurdle, a pooled direct model and a prespecified adaptive rule were evaluated. The locked selection was written before the holdout, and the holdout uses a separate seed-2026 catalog sample, disjoint from both the 60-pair development sample and the earlier 12-pair sample. The holdout origin is 2016-03-27, training dates 2015-03-29 through 2016-03-27, and evaluation dates 2016-03-28 through 2016-04-24. All 30 selected pairs were eligible, giving 840 pair-days per method. The sample contains 16 FOODS, 10 HOUSEHOLD and 4 HOBBIES pairs, spread across 10 stores and all three states.

Before examining holdout results, the development lock chose lowest pooled WAPE in the TSB, SBA, moving average and LightGBM grids, and retained TSB 0.1, moving average 28, zero, hurdle, pooled direct, the predeclared adaptive rule and Poisson for its development RMSE. It is stored as `research_output/optimization_dev_v143/locked_candidates.json`.

## Development results

Lowest pooled WAPE was LightGBM L1 62.312% with MAE 1.709, RMSE 3.645 and signed bias -0.683. TSB 0.1 yielded 65.648%; moving average 14 yielded 66.080%; the adaptive rule 67.262%; hurdle 68.475%; and direct 70.218%. LightGBM Poisson achieved RMSE 3.521 with WAPE 68.081%. The grid and fold metrics are saved as artifacts. These outcomes are selected from development data and are not independent confirmation.

## Locked independent holdout

| Model | MAE | RMSE | WAPE % | Bias | Mean valid RMSSE |
|---|---:|---:|---:|---:|---:|
| LightGBM L1 | 1.291 | 2.331 | 68.079 | -0.626 | 0.870 |
| Moving average 28 | 1.314 | 2.226 | 69.290 | -0.036 | 0.800 |
| Moving average 14 | 1.318 | 2.264 | 69.500 | -0.011 | 0.798 |
| TSB 0.1 | 1.322 | 2.252 | 69.709 | -0.002 | 0.796 |
| Adaptive | 1.323 | 2.245 | 69.773 | 0.001 | 0.795 |
| Direct | 1.354 | 2.295 | 71.419 | 0.056 | 0.802 |
| SBA 0.05 | 1.402 | 2.368 | 73.950 | -0.133 | 0.827 |
| LightGBM Poisson | 1.441 | 2.514 | 75.976 | 0.025 | 0.834 |
| Hurdle | 1.446 | 2.477 | 76.264 | 0.054 | 0.838 |
| Zero | 1.896 | 3.509 | 100.000 | -1.896 | 1.103 |

All 30 per-series RMSSE denominators were defined. These are unweighted scoped averages, not official M5 WRMSSE. Pooled WAPE sums absolute errors before division. Positive bias means overprediction.

L1 achieved the lowest pair-level WAPE by 1.21 percentage points versus the 28-day moving average, but its mean bias was -0.626 units per pair-day. On the sampled total, its WAPE was 34.991% compared with 21.030% for TSB and adaptive. At the store level these values were 46.067%, 41.709% and 42.227%, respectively. Pair-level and aggregate objectives therefore disagree in this sample. These aggregates represent the sampled pairs only.

Cumulative WAPE at 7 / 14 / 28 days was 67.732 / 63.835 / 68.079% for L1, 72.053 / 64.553 / 69.709% for TSB and 72.944 / 64.984 / 69.773% for adaptive. These horizons overlap. The holdout has one origin and is insufficient to measure temporal stability.

For low-demand histories, L1 / TSB WAPE was 104.160 / 118.698%; for medium demand it was 61.200 / 59.168%; for high demand 67.489 / 73.897%. These percentages are sensitive to the actual-demand denominator. There were no zero-average histories in this small holdout.

## Drift and failure analysis

The earlier V1.4.2 development predictions were positive on essentially every pair-day, while observed positive-demand fractions were 54.4%, 54.3% and 51.6% in days 1–7, 8–14 and 15–28. The expanded feature pipeline treats any positive recursive prediction as a nonzero event, which can shift nonzero-frequency features when fed point forecasts. Positive expected demand is not a predicted probability of occurrence. This observation suggests a plausible feedback mismatch, but the experiment does not isolate it causally. The hurdle model explicitly separates occurrence probability and conditional positive magnitude, yet did not beat TSB on this holdout.

The holdout illustrates a trade-off rather than a clear winning deployment strategy. L1 lowers pair-level MAE and WAPE by predicting low values, while underestimating sampled aggregate demand. The adaptive policy kept near-zero mean bias, but did not materially improve on TSB. The direct model avoided recursive feature feedback and achieved 71.419% WAPE, also behind the simpler references.

Holdout training/prediction times in seconds were 0.262/0.334 for L1, 0/0.197 for TSB, 0.331/0.439 for hurdle, and 7.227/0.102 for direct, excluding shared feature preparation of 0.125 seconds and extraction. Direct training includes creation of lead-expanded examples. Peak memory was not recorded.

## Tracking and limitations

MLflow experiment 4 contains development run `c049d8f2840b422b99c9528a009d33f8` and holdout run `9b83c22186a44708af425316e38939cc`. Results, locked settings, source copies and charts are retained in those runs and locally under ignored `research_output/optimization_dev_v143/` and `research_output/optimization_holdout_v143/`. Candidate alias remained version 1.

One small independent cohort and one holdout origin do not establish robust selection. Demand is sampled from historical M5 data, coverage excludes any incomplete series and no population weighting is applied. The direct model uses origin-snapshot calendar fields plus lead, and the hurdle model is a basic point-forecast method. The evaluated adaptive rule is a prespecified heuristic rather than a calibrated policy. No serving candidate is packaged because the small WAPE advantage of L1 comes with substantial negative bias and weaker aggregate accuracy. No production registry model was promoted.

Exact commands and methodological safeguards are in [the protocol](v1_4_3_optimization_protocol.md).
