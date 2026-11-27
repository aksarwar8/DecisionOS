# DecisionOS forecasting research

The [production performance notes](docs/research/production_performance_evaluation.md) describe descriptive drift diagnostics; no new performance benchmark is claimed.

DecisionOS studies daily product-store demand on the historical M5 retail data. Demand is heterogeneous, contains many zero observations and is evaluated at multiple business aggregation levels. The project asks whether learned recursive forecasts improve on simple methods, how performance varies by demand segment, origin and horizon, how geography and category affect errors, and what computation costs.

The existing policy trains a Random Forest on calendar and lag features and substitutes the historical mean for the zero-average segment. The recorded April 2011 28-day evaluation reports hybrid WAPE 77.03%. A separate four-fold seven-day evaluation reports mean fold WAPE 73.229%. These are different scopes and must not be combined. See [28-day results](docs/experiments/hybrid_model_evaluation.md) and [rolling results](docs/experiments/rolling_origin_backtest.md). The earlier reports do not establish performance across the entire M5 history.

The new exploratory protocol trains 30-tree research forests independently at each 2015 origin and compares nine reference methods on 12 uniformly sampled catalog pairs. Pooled 28-day WAPE was 92.09% for TSB, 93.28% for the 28-day moving average, and 102.33% for both the Random Forest and hybrid. These are measurements for 24 pair-folds, not evidence of population-wide ranking. The experiment report records scope, errors and limitations.

The official M5 evaluation uses weighted RMSSE across a hierarchy and sales-value weights. DecisionOS currently supplies a per-series training-scaled RMSSE function. It is not official WRMSSE. [M5 competition paper](https://doi.org/10.1016/j.ijforecast.2021.11.013)

Croston estimates nonzero size and interarrival time separately. SBA reduces its forecast bias under its assumptions, while TSB updates the probability of demand each period and can react to obsolescence. Parameter choices, initialization and limitations are described in the [learning guide](docs/engineering/v1_4_1_forecast_evaluation_learning_guide.md). [Syntetos and Boylan](https://www.sciencedirect.com/science/article/pii/S0925527300001432), [Teunter et al.](https://pure.rug.nl/ws/portalfiles/portal/145394864/Intermittent_demand_Linking_forecasting_to_inventory_obsolescence.pdf)

Detailed hypotheses, origin definitions, leakage controls and commands are in the [protocol](docs/research/v1_4_1_experiment_protocol.md). Measured findings and open questions are in the [benchmark report](docs/research/v1_4_1_forecasting_benchmark_report.md). Future research should evaluate stratified training-history cohorts, longer horizons, full hierarchical scoring, variance across seeds, and a held-out final period. LightGBM was not trained or compared in that initial run; subsequent studies are described below.

## Stratified follow-up

A separate 60-pair, three-origin study uses a 360-pair seeded catalog pool and train-only joint strata. It covers all ten stores, three categories, all existing demand segments and multiple intermittent-demand classes. Pooled 28-day WAPE was 65.65% for TSB, 68.15% for a 28-day moving average, 69.16% for LightGBM and 101.98% for the 100-tree Random Forest. The deliberately stratified cohort is not population weighted. The [benchmark report](docs/research/v1_4_1_forecasting_benchmark_report.md) preserves both this study and the earlier 12-pair result, and details uncertainty, subgroup denominators and failure examples.

Syntetos, Boylan and Croston develop demand categorization using average inter-demand interval and variation of positive demand sizes. This repository uses common 1.32 and 0.49 cutoffs as descriptive approximations, with all-zero and insufficient-positive histories explicitly separate. These classes do not change the production policy. [Original research](https://doi.org/10.1057/palgrave.jors.2601841), [discussion of classification boundaries](https://robjhyndman.com/papers/idcat.pdf).

V1.4.2 review found that the V1.4.1 “LightGBM” comparison included the hybrid zero-average substitution. The recorded metric remains historical evidence for that combined policy and should not be described as standalone LightGBM. The research runner now routes standalone LightGBM through recursive forecasting.

## V1.4.2 feature research

On the same 60-pair development cohort and identical forecast targets, standalone canonical LightGBM had pooled WAPE 69.70%. Demand/intermittency features increased it to 75.87%, and the full feature set to 76.62%. The earlier TSB reference was 65.65%. This evidence favors additional validation over adopting the expanded contract. It does not establish population-wide performance. [Feature ablation report](docs/research/v1_4_2_feature_ablation_report.md)

The previous V1.4.1 LightGBM result included the hybrid historical-mean substitution on zero-average histories because of its dispatch path. It remains a valid recorded combined-policy result, but should not be interpreted as standalone LightGBM. The V1.4.2 A model uses standalone recursive LightGBM.

Calendar events and state SNAP are treated as scheduled at the origin. Quote history is restricted to completed weeks and frozen during prediction. [LightGBM categorical handling](https://lightgbm.readthedocs.io/en/latest/Advanced-Topics.html) and [M5 competition results](https://doi.org/10.1016/j.ijforecast.2021.11.013) inform design choices without establishing causality.

## Research direction

The project roadmap prioritizes adaptive forecasting, independently validated model selection, uncertainty, scalable inference, operational risk, inventory and cost-aware decisions. Subsequent engineering milestones cover explainability, reproducible deployment, model management, monitoring and drift. Candidate integration remains subject to independent evaluation and user approval. Generative and agentic AI research belongs to a separate project; DecisionOS exposes capabilities through its existing API boundaries.
## V1.4.3 optimization study

A locked comparison used 60 development pairs across three 2015 origins, then 30 disjoint catalog-sampled pairs at a March 2016 holdout origin. Development L1 LightGBM achieved 62.31% pooled WAPE. On the independent holdout L1 achieved 68.08% pair-level WAPE and -0.626 mean signed bias, versus 69.71% and -0.002 for TSB; the adaptive policy achieved 69.77% pair-level WAPE. LightGBM substantially underestimated aggregate demand. At the sampled-total level L1 WAPE was 34.99%, compared with 21.03% for TSB. These results do not support replacing the served model.

The experiment includes smoothing and moving-window grids, several LightGBM objectives, a two-stage occurrence/positive-size model, a pooled direct lead model and a fixed train-only demand-classification policy. The same locked methods and eligible dates were compared on the holdout. Both research MLflow runs and the candidate alias were verified. See the [protocol](docs/research/v1_4_3_optimization_protocol.md) and [report](docs/research/v1_4_3_optimization_report.md).

Recursive drift was investigated descriptively: positive point predictions became inputs to nonzero-frequency features, while many actual days had no demand. These point predictions are expected quantities and do not themselves encode event probabilities. A causal contribution of this feedback has not been established.

## Predictive intelligence evaluation

The integrated baseline strategies and empirical intervals are described in the [predictive evaluation](docs/research/predictive_intelligence_evaluation.md). In a single controlled synthetic 28-day evaluation, nominal 80% intervals covered 64.29% of outcomes and nominal 95% intervals covered 100%. This illustrates why nominal coverage should be tested on further independent chronological data. A three-spike synthetic anomaly check yielded precision and recall 1.0 only on that constructed sample.

## Prescriptive simulation

A bounded 62-day historical replay for product 4/store 1 compared simulated inventory policies using past-only 28-day average demand estimates. Under one illustrative cost set, forecast-driven replenishment achieved a 99.1% simulated fill rate and 283.46 cost units, while no replenishment achieved 10.3% and 420.78. A lower shortage penalty changed the cost ranking. These are assumptions and historical sales proxies, not real inventory, measured savings or population-level results. [Evaluation and sensitivity](docs/research/prescriptive_intelligence_evaluation.md)
