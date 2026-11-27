# V1.4.3 model optimization protocol

The development study reuses the V1.4.1 60-pair cohort and the three 2015 origins. Each fold trains on the preceding 365 daily observations and predicts the next 28 days. Before examining these results, the planned selection is the lowest pooled development WAPE within each of the TSB, Croston SBA, moving-average and LightGBM objective groups, alongside the predeclared adaptive rule, the hurdle model, direct model and TSB 0.1 reference. The fixed grid uses smoothing 0.05, 0.1, 0.2, 0.3 and moving windows 7, 14, 28, 56, 90. LightGBM compares L2, L1, Poisson, Tweedie power 1.2 and a smaller-tree L2 configuration, with 60 estimators.

The adaptive hypothesis uses TSB 0.1 for intermittent, lumpy, zero and insufficient-positive histories and a 28-day moving average for smooth or erratic histories. Classification uses only each fold's training history. It is an interpretable fixed policy, not a tuned per-series oracle.

The hurdle method estimates occurrence probability using a classifier and positive quantity using a regressor. Their product is recursive expected demand. For all-zero training targets it returns zero. The pooled direct approach trains a single model with lead 1–28 on historical snapshots spaced seven days apart; each target must exist within the training fold. At inference it predicts every lead from the same origin snapshot. Its calendar fields describe that snapshot, with lead supplied separately. It is not 28 separately fitted horizon models.

After the development comparison the selection is recorded in a lock file. A seeded uniform catalog sample excludes the 60 development pairs. The untouched holdout origin is 2016-03-27, with target dates 2016-03-28 through 2016-04-24. Its training window ends at the origin. Cohort selection uses catalog identifiers only and never holdout demand. The same eligible pair-date keys are required across methods; missing windows are reported. The small holdout is a diagnostic sample, not a population-wide claim. Do not tune on its results.

MAE, RMSE, pooled WAPE, bias and train-scaled per-series RMSSE follow the V1.4.1 definitions. Hierarchical scoring sums pair predictions and observations at the same date before scoring. Feature preparation, model fit and inference times are recorded separately. The statistical baseline grid is limited and makes no claim of global parameter optimization.

LightGBM documents the chosen objectives in its [official parameter reference](https://lightgbm.readthedocs.io/en/latest/Parameters.html). A two-stage occurrence/quantity decomposition is discussed in [Reframing demand forecasting](https://arxiv.org/abs/2103.13812). Neither reference implies a model will win on this cohort.

Reproduce the development run in a new output directory, lock the selections from the reproduced development scores, and then run the holdout only when it remains unused:

```powershell
.\.venv\Scripts\python.exe -m experiments.forecasting.optimize --mode dev --pairs 60 --mlflow --output research_output/optimization_dev_new
.\.venv\Scripts\python.exe -m experiments.forecasting.lock_candidates research_output/optimization_dev_new
.\.venv\Scripts\python.exe -m experiments.forecasting.optimize --mode holdout --pairs 30 --lock research_output/optimization_dev_new/locked_candidates.json --mlflow --output research_output/optimization_holdout_new
.\.venv\Scripts\python.exe -m experiments.forecasting.plot_optimization research_output/optimization_dev_new
```

The 2016 holdout has now been evaluated once. Re-running this exact configuration is a reproduction, not a fresh independent confirmation. The output directory guard prevents accidental overwrite.
