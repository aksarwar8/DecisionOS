# V1.4.1 bounded forecasting benchmark

This exploratory run used 12 uniformly sampled catalog pairs, seed 42, across three categories and three states. It used 365 calendar days per fold, origins 2015-04-30 and 2015-10-31, and the following 28 days as targets. All 12 pairs were eligible in each fold. There were 24 pair-folds and 672 target rows per method. The model was retrained at each origin with 30 trees. This is a small convenience experiment and does not establish full M5 performance.

| Method | MAE | RMSE | Pooled WAPE % | Mean signed bias |
|---|---:|---:|---:|---:|
| TSB | 0.606 | 0.978 | 92.088 | -0.021 |
| Moving average | 0.614 | 0.970 | 93.277 | 0.016 |
| Zero | 0.658 | 1.265 | 100.000 | -0.658 |
| SBA | 0.659 | 0.989 | 100.163 | 0.020 |
| Naive | 0.667 | 1.168 | 101.357 | -0.199 |
| Croston | 0.668 | 0.992 | 101.609 | 0.056 |
| Random Forest | 0.673 | 1.033 | 102.332 | 0.142 |
| Hybrid | 0.673 | 1.033 | 102.332 | 0.142 |
| Historical mean | 0.714 | 1.029 | 108.489 | 0.044 |
| Seasonal naive 28 | 0.787 | 1.349 | 119.683 | 0.016 |
| Seasonal naive 7 | 0.792 | 1.387 | 120.362 | -0.003 |

Pooled WAPE sums absolute errors and actual demand across both folds before division. It is different from the arithmetic mean of fold WAPEs printed by the runner. For the first 7 forecast days, pooled WAPE was 85.63% for moving average, 85.74% for TSB and 97.24% for RF. For the first 14 days it was 86.25%, 85.87% and 97.81%, respectively. For 28 days the corresponding values are 93.28%, 92.09% and 102.33%. The target periods overlap across these horizon summaries.

Across both folds, research forest training took about 1.02 seconds in total. Recursive prediction took 3.24 seconds for the forest and 2.66 seconds for the hybrid, which reuses the same trained forests. Baseline predictions took 0.03–0.06 seconds per method in total. These are in-process timings on this run and do not include extraction. The identical RF and hybrid metrics in this sample do not establish equivalence for zero-history series.

This run does not report segment-specific results, correct per-series RMSSE, hierarchy scores, memory use or representative failure cases. It did not benchmark LightGBM or assess the final holdout. It provides no full-business result. The fixed cohort did not guarantee all demand segments or all ten stores. Further experiments should predefine a stratified training-history cohort, persist train-only segment labels, calculate per-series RMSSE, aggregate matched forecasts by hierarchy, examine failures, and compare multiple seeds.

The script writes its sampled pair manifest, configuration, per-fold results, exclusion list and predictions under ignored `research_output/bounded/`. A two-pair smoke run was completed first. The optional MLflow path was not exercised in this initial experiment; the stratified follow-up verified it. No registry alias was changed.

## Stratified follow-up — three origins, 60 pairs

The follow-up uses seed 42 to sample a 360-pair catalog pool. Its earliest 365-day training window, 2014-05-01 through 2015-04-30, defines eligible pairs and initial strata. Joint category, state, existing demand segment and research classification strata are sampled in round-robin order after seeded shuffling. This deliberately oversamples rare observed strata and is not population weighted. All 360 pool pairs had complete initial history. The 60 selected pairs cover all 10 stores.

Initial production segments are 3 zero-average, 21 low, 26 medium and 10 high. Initial research classifications are 3 all-zero, 1 insufficient-positive, 14 smooth, 6 erratic, 19 intermittent and 17 lumpy. Category counts are 33 FOODS, 11 HOBBIES and 16 HOUSEHOLD. State counts are 28 CA, 17 TX and 15 WI.

Training windows end at 2015-04-30, 2015-07-31 and 2015-10-31. The first windows start on 2014-05-01, 2014-08-01 and 2014-11-01 respectively. All 60 pairs had complete training and target observations at every origin. Each method has 5,040 28-day rows. Forecasts at 7, 14 and 28 days are overlapping prefixes. The saved horizon-bucket summary separately reports days 1–7, 8–14 and 15–28.

| Method | MAE | RMSE | Pooled WAPE % | Bias |
|---|---:|---:|---:|---:|
| TSB | 1.801 | 3.687 | 65.648 | -0.080 |
| Moving average | 1.870 | 3.838 | 68.154 | -0.012 |
| LightGBM | 1.897 | 3.628 | 69.158 | 0.308 |
| Historical mean | 2.098 | 4.005 | 76.499 | 0.079 |
| SBA | 2.131 | 4.063 | 77.705 | 0.017 |
| Seasonal 7 | 2.153 | 4.309 | 78.503 | -0.041 |
| Croston | 2.158 | 4.090 | 78.660 | 0.163 |
| Naive | 2.221 | 4.631 | 80.962 | -0.115 |
| Seasonal 28 | 2.307 | 4.904 | 84.116 | -0.012 |
| Zero | 2.743 | 5.891 | 100.000 | -2.743 |
| Hybrid | 2.752 | 4.748 | 100.327 | 1.366 |
| Random Forest | 2.797 | 4.779 | 101.982 | 1.414 |

The pooled result uses sums of absolute errors and actuals across pair-folds, rather than mean fold WAPE. The 100-tree Random Forest uses the same hyperparameters as the existing training function. LightGBM 4.7.0 uses 100 estimators, maximum depth 15, seed 42 and two CPU threads with the same feature columns. No model is promoted.

For low-demand pair-folds TSB, LightGBM and RF WAPE were 111.39%, 142.86% and 442.22%. For intermittent histories they were 69.83%, 79.97% and 189.76%. For lumpy histories they were 85.92%, 91.31% and 140.41%. A low actual denominator can make WAPE large. In the initial 12-pair sample RF and hybrid were identical because the reconstructed training windows contained 18 low-demand and 6 medium-demand pair-folds, so the hybrid selected Random Forest for all 24. In this follow-up five pair-folds had zero training average, and the policy reduced their pooled WAPE from 888.90% for RF to 100% for hybrid.

Cumulative WAPE for days 1–7, 1–14 and 1–28 was 58.62%, 61.41%, 65.65% for TSB; 56.30%, 62.69%, 69.16% for LightGBM; and 84.65%, 93.83%, 101.98% for RF. These figures cannot isolate recursive error accumulation because the target composition changes. Disjoint bucket results are in `summary_horizon_bucket.csv`.

Sample-cohort WAPE after aggregating predictions and actuals by date was, for TSB / LightGBM / RF: product 64.58 / 67.98 / 100.81%, store 38.95 / 39.71 / 69.74%, category 23.79 / 24.01 / 58.03%, state 26.66 / 26.84 / 58.20%, and total sampled cohort 17.12 / 16.54 / 54.10%. These are sampled-pair aggregates. Per-series 28-day RMSSE was defined for 175 of 180 pair-folds. Mean valid RMSSE was 0.699 for TSB, 0.799 for LightGBM and 2.117 for RF and hybrid. Five constant training histories have undefined scale. Leading zeros are retained. These are unweighted scoped RMSSE averages, not M5 WRMSSE.

Training took 8.23 seconds summed over the three RF folds and 1.08 seconds for LightGBM. Prediction took 6.81 seconds for RF, 7.13 for hybrid, 1.65 for LightGBM and 0.42 for TSB. RF and hybrid share each trained forest, so do not add their training times. These timings exclude extraction and feature setup. Peak memory was not measured.

One high-error case was product 2948, store 10, at the October origin. Actual demand was zero across 28 days while RF predicted 479.02 total units. Another, product 2427/store 10 at the July origin, had 329 actual units, predicted 639.46 and a daily peak of 52. These are observed errors. The reasons remain hypotheses. Possible effects include changing demand and recursive lag feedback. The study does not establish causality.

Artifacts, charts, per-series scores, fold profiles and full cohort are under ignored `research_output/stratified_60/`. MLflow experiment ID 2, run `67bc95770eca442ab31cf16fe17df114`, is FINISHED with metrics, parameters and analysis artifacts. Candidate alias resolved to version 1 on verification. A metadata write initially failed because MLflow parameters are immutable; the run was resumed with non-conflicting keys and verified.

This one seeded pool, three origins and deliberately balanced sample do not represent population-level M5 model ranking. Training-only demand classification does not explain why observations change. Target completeness controls eligibility for evaluation, and all selected pairs were complete in this run. Research comparisons preserve the same aligned pairs, dates and features. A final chronological holdout remains untouched. The exact earlier 12-pair results remain above; the runner now uses stratified selection and its earlier uniform selection command no longer reproduces that initial sample without its saved manifest.

## Correction discovered during V1.4.2

The V1.4.1 runner dispatched the LightGBM model through `hybrid_forecast`. Thus the reported LightGBM numbers include the production historical-mean substitution for zero-average histories. The label “LightGBM” in the saved run represents LightGBM with that hybrid substitution, rather than standalone LightGBM. The 69.16% WAPE is preserved as originally measured. This does not change the Random Forest, TSB or moving-average results. The runner has been corrected for future standalone LightGBM runs. The V1.4.2 ablation trains standalone LightGBM for each feature configuration and reports matched reference values separately.
