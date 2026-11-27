# V1.4.2 feature ablation protocol

The fixed development cohort is the saved 60-pair V1.4.1 cohort. Its three 2015 origins and 28-day targets are reused. The 2016 chronological holdout remains untouched. The selected cohort is stratified and not population weighted. All configurations use identical pairs and target dates and train on days 91–365 of each 365-day history so the largest lag has 90 days of warmup.

Hypotheses before the run: short recent history and intermittency features may reduce low-demand overprediction; scheduled calendar and SNAP features may help seasonal variation; price histories may help only if historical quotes contain useful information. Each could fail or increase error.

Configuration A uses the production canonical 14 features. B adds 12 recent-demand and six intermittency features. C adds 11 scheduled calendar/event features. D adds state-specific SNAP and seven price-history features. E adds three metadata codes to canonical and marks product/store and metadata identifiers as categorical. F combines every family with LightGBM categorical handling. A–D retain numeric identifiers, preserving the initial canonical convention. Differences between D and F include categorical treatment as well as added metadata.

Historical windows use actual observations until an origin and previous model predictions after it. A nonzero-frequency feature counts any strictly positive recursive prediction as nonzero, which can distort intermittent-demand behavior. Rolling means, lag values and standard deviations exclude the target. The recent exponential mean uses 90 previous observations, span 28 and adjust=False. Undefined ratios, all-zero ADI and insufficient positive-size variance remain missing for LightGBM.

Calendar event slots and SNAP are treated as known from the schedule at origin. Event name/type vocabularies are fitted from each fold's training calendar, and unseen categories map to -1, treated as missing by categorical LightGBM. Calendar event codes in noncategorical configurations are ordinal numeric codes, a limitation. The two event flags represent both slots. Separate days-to-event and days-since-event features are not implemented.

Price quotes are matched by unique pair and week. Any duplicate pair-week or calendar date causes the experiment to stop. A quote becomes available only after its complete week ends, and only quotes strictly before the feature cutoff are used. Historical training rows use past completed weeks; the forecast freezes quotes at the origin. Missing price values are represented explicitly, never as zero. This is a conservative as-of policy, not an assumption that future actual prices were known. The observed quote is not assumed to be a promotion, causal price effect or stock-availability indicator.

Reproduce after installing the optional dependencies in `requirements-research.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt
.\.venv\Scripts\python.exe -m experiments.forecasting.feature_ablation --pairs 60 --mlflow --output research_output/feature_ablation_v1_new
.\.venv\Scripts\python.exe -m experiments.forecasting.summarize_ablation research_output/feature_ablation_v1_new
```

The runner refuses to overwrite an existing output directory. The source and results are research-only and do not alter production serving.

LightGBM's categorical documentation describes integer category handling and missing values. [LightGBM documentation](https://lightgbm.readthedocs.io/en/latest/Advanced-Topics.html). M5 competition work motivates testing calendar and price covariates, without implying that they are causally responsible for an observed change. [M5 accuracy results](https://doi.org/10.1016/j.ijforecast.2021.11.013).
