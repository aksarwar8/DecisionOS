# V1.4.2 feature ablation report

## Scope and measured results

The development experiment reused all 60 saved stratified pairs and the three origins 2015-04-30, 2015-07-31 and 2015-10-31. Each origin had 365 training days, of which the first 90 were feature warmup, and 28 evaluation days. Every configuration used the same 5,040 evaluation rows. The prior V1.4.1 TSB, moving average, Random Forest and hybrid forecasts were matched against the same product-store-date-actual keys. The V1.4.1 “LightGBM” result included the hybrid zero-average substitution; A here is standalone LightGBM.

| Configuration | Features | MAE | RMSE | Pooled WAPE | Bias | Mean valid RMSSE |
|---|---:|---:|---:|---:|---:|---:|
| A canonical | 14 | 1.912 | 3.739 | 69.695% | 0.289 | 0.797 |
| B demand and intermittency | 32 | 2.081 | 3.869 | 75.873% | 0.641 | 0.859 |
| C B + calendar/events | 43 | 2.084 | 3.904 | 75.958% | 0.603 | 0.866 |
| D C + SNAP/price | 51 | 2.093 | 3.928 | 76.307% | 0.646 | 0.873 |
| E canonical + categorical metadata | 17 | 1.931 | 3.671 | 70.404% | 0.382 | 0.756 |
| F combined | 54 | 2.102 | 3.954 | 76.620% | 0.632 | 0.839 |

RMSSE averages 175 valid pair-fold scores; five constant training histories have undefined scales. TSB and 28-day moving average references had pooled WAPE 65.648% and 68.154%. The prior 100-tree Random Forest reference had 101.982% and hybrid 100.327%. Their training rows began after the original 28-day warmup, whereas ablations use a 90-day warmup, so comparisons across those model families do not control for training-row count. All ablation configurations do share the same training rows.

On the pooled data, adding the demand family increased WAPE by 6.178 percentage points relative to A. Adding calendar/events to B increased it by 0.085 points, and SNAP/price to C increased it by 0.349 points. E had lower RMSE and mean valid RMSSE than A, but a 0.709-point higher WAPE. F increased WAPE by 6.925 points relative to A. This single development cohort does not establish that any feature family is broadly harmful or useful.

For intermittent training histories, A / B / F / TSB WAPE was 75.96 / 81.23 / 79.19 / 69.83%. For lumpy histories it was 90.97 / 116.99 / 113.94 / 85.92%. For low-demand histories it was 140.40 / 150.10 / 139.30 / 111.39%. These group denominators differ and can be small.

Cumulative 7 / 14 / 28-day WAPE was 56.61 / 63.23 / 69.70% for A, 63.96 / 70.51 / 75.87% for B and 66.01 / 71.97 / 76.62% for F. Horizons overlap. Fold WAPE for A was 63.10 / 80.62 / 65.04%; for F it was 68.91 / 75.72 / 85.49%. F improved over A in the July-origin fold but was worse in the other two.

After summing matched forecasts and actuals before scoring, sampled-cohort WAPE for A / F was 68.38 / 75.42% at product, 40.39 / 45.61% at store, 24.74 / 31.85% at category, 26.69 / 33.12% at state, and 16.38 / 24.81% for the sampled total. These are sample aggregates, not business-wide forecasts.

## Diagnostics

For the known product 2948/store 10 October-origin case, actual demand was zero. Predicted 28-day totals were 10.24 units for A, 13.61 for B, 4.93 for E and 7.50 for F. The earlier RF predicted 479.02. The case was selected because it was already known to fail and is exploratory. It does not establish typical improvement.

In F, the largest summed LightGBM gain across folds was rolling_mean_7 (4,443,113), followed by ewm_28 (298,509), lag_1 (291,683), product_id (186,129), and mean_14 (167,401). Family gain totals were canonical 5,327,364; advanced demand 1,386,207; intermittency 256,286; calendar 82,685; pricing 31,998; metadata 28,859; and SNAP 16,455. Gain depends on tree structure and correlated alternatives. Related rolling windows, EWM, mean ratios and momentum overlap in information. No formal correlation or permutation analysis was run, so redundancy is a hypothesis rather than a measured removal decision. Gain does not show causality.

Shared preparation took 57.75, 39.72 and 48.38 seconds per fold. Across all folds, LightGBM model fitting took 0.72 seconds for A and 2.12 seconds for F. Recursive inference took 11.79 and 20.72 seconds respectively. Preparation computes the full feature set once per fold even for A, so this is not A-only production latency. A process memory check during the run observed 311 MB peak working set at that moment; final peak was not measured.

The 60-pair cohort is stratified, unweighted and reused for development. No second-seed sample, independent holdout, RF retraining under the new configurations, permutation importance, days-to-event features, price interaction study or population claim is included. Missing price quotes are not assumed to indicate stockouts. Event/SNAP data is treated as scheduled information. The full audit, definitions and reproducibility commands are in the [protocol](v1_4_2_feature_engineering_protocol.md).

Results and plots are under ignored `research_output/feature_ablation_v1/`. MLflow experiment 3, run `1198e159496e4339b0bc2cb53db376e2`, was read back as FINISHED with 44 metrics and source and analysis artifacts. The candidate alias still resolved to version 1. The source was uncommitted at execution; source hashes and copies are attached to the run.
