# V1.4.1 experiment protocol

Research questions RQ1–RQ7 concern baseline improvement, demand segments, origin stability, horizons, category and state variation, computational cost, and failure modes. Before observing results, we hypothesize that seasonal naive may help weekly patterns, intermittent methods may help sparse series, and recursive errors may increase with horizon. Any method can win.

The exploratory runner samples product-store catalog pairs uniformly with a fixed seed before reading validation demand. It uses 365 training days ending at each origin, then 28 future days. It retrains a 30-tree Random Forest at each origin with the existing 14-feature contract and compares its recursive predictions and the existing hybrid policy to nine fixed baselines. The forest is a reduced-cost research configuration. The production registry is untouched.

The forecasts for 7 and 14 days are the first 7 or 14 days of the same 28-day forecast, with no later actuals fed back. All models use identical pairs within a fold. Pairs with incomplete train or target windows are excluded and recorded. Excluding incomplete targets makes the reported result conditional on available observations. Catalog sampling does not guarantee balance by demand segment, state or category.

A final chronological holdout is reserved for future confirmation and must not be used for tuning. This exploratory protocol uses 2015-04-30 and 2015-10-31 origins, with a 2016 holdout not evaluated here. An expanding window or stratified train-only segment sampling are useful future variations. A 365-day sliding window enables bounded comparison.

For every forecast origin, training includes the origin date, and forecast dates start on the next day. Feature construction uses only training data and recursive model predictions. No demand from validation dates is used in historical means, segment assignment or model fitting. Complete target coverage is used solely to define scoreable records, never to select training pairs.

Commands from the repository root:

```powershell
.\.venv\Scripts\python.exe -m experiments.forecasting.run_benchmark --pairs 2 --origins 2015-04-30 --trees 5 --output research_output/smoke
.\.venv\Scripts\python.exe -m experiments.forecasting.run_benchmark --pairs 12 --trees 30 --output research_output/bounded
```

The extraction queries only selected pairs and bounded dates using parameterized SQL and a 25-second statement timeout. CSV predictions, cohort IDs, fold metrics, exclusions and run configuration are written locally. Each fold writes its outputs before the next fold, preserving completed fold data after interruption.

The optional --mlflow flag logs the completed run into the separate DecisionOS-forecast-research experiment using the existing configured tracking store. The stratified follow-up verified this integration in experiment 2, run 67bc95770eca442ab31cf16fe17df114. It does not update model aliases.

## Stratified follow-up

The follow-up draws a fixed seeded catalog pool, evaluates characteristics using the earliest training window only, then samples the observed joint category/state/segment/classification strata in round-robin order. This balances the observed strata, not the full population. Every later fold recomputes production and research classifications from its own training history. Missing or incomplete windows are recorded as exclusions.

Average inter-demand interval is training-window length divided by nonzero-day count. CV² is the population variance of positive demand divided by its mean squared. This implementation assigns ADI < 1.32 and CV² < 0.49 to smooth, ADI < 1.32 and CV² ≥ 0.49 to erratic, ADI ≥ 1.32 and CV² < 0.49 to intermittent, and the remainder to lumpy. All-zero and fewer than two positive observations receive explicit separate labels. The thresholds are approximations from a method-comparison framework and should not be treated as causal rules. [Syntetos, Boylan and Croston](https://doi.org/10.1057/palgrave.jors.2601841), [Hyndman and Kostenko](https://robjhyndman.com/papers/idcat.pdf).

For reproduction, with LightGBM 4.7.0 and matplotlib 3.11.2 available in the existing environment:

```powershell
.\.venv\Scripts\python.exe -m experiments.forecasting.run_benchmark --pairs 60 --pool 360 --trees 100 --lightgbm --output research_output/stratified_60
.\.venv\Scripts\python.exe -m experiments.forecasting.summarize_benchmark research_output/stratified_60
```

Add `--mlflow` to log a new research run to the configured existing store. It creates or uses a separate experiment and does not promote models. Each completed fold writes prediction and per-series score artifacts. In this run, fold characteristics were reconstructed afterward from the same training windows. Source provenance is the checkpoint hash plus uncommitted research code. Catalog pool metadata is now saved by subsequent runs. The completed run pool was reconstructed afterward from the same catalog and seed, and verified to contain all selected pairs.
