# V1.4.2 feature engineering learning guide

Production still uses its existing 14 columns: numeric product and store IDs; year, month, day, day of week, ISO week and weekend; lags 7, 14 and 28; means over the previous 7 and 28 days; and sample standard deviation over the previous 7 days. The training pipeline sorts each series, shifts demand before rolling and drops rows without complete lag features. Transform data types are compact integers where safe. Recursive serving constructs the same ordered vector and appends predictions, not future actuals.

The research-only pipeline lives in `src/decisionos/evaluation/experimental_features.py`. A feature family is a named list of columns, and `columns` produces the requested ordered contract. The same `feature_row` function is called for past training examples and recursive future predictions. Ninety earlier observations are required for every training target. The research pipeline does not change the production model.

Advanced demand adds lags 1, 2, 56 and 90; means over 14 and 56 days; 28-day standard deviation, minimum and maximum; a 28-span exponential mean on the last 90 days; and 7-versus-28 mean difference and ratio. The ratio is missing when its denominator is zero.

Intermittency features are recent nonzero frequency, zero frequency, days since a nonzero observation, ADI, average positive size and positive-size CV². During recursion any positive model prediction counts as nonzero. A point forecast may be positive even if the actual day would have zero demand, so these features can drift during a long horizon.

Calendar features include quarter, cyclical weekday/month, both event slots and train-only integer vocabularies for event name and type. SNAP uses the indicator for the store state. Price features consider only completed weeks before the cutoff, with the origin cutoff frozen for future dates. Feature availability is distinct from a zero price, and no currency is assumed.

Training and serving parity matters because a model trained on a different definition from the one used in prediction will see a changed input distribution. The synthetic test compares all canonical values to the production recursive function, then checks that an appended prediction changes the next day's lag. Testing future-price cutoff, unknown categories, two event slots and state SNAP prevents common data-leakage mistakes.

Study the feature module, its synthetic tests, the ablation runner, then the protocol and report. Feature importance shows which splits a tree used, not why customers purchased an item. Shared rolling windows can be correlated, so gain is not a unique causal contribution.

Interview question: Why freeze future prices at the forecast origin? The realized price of a later week may be unknown then. A historical-only scenario prevents the backtest from using privileged future information. Why compare ablations on the same targets? Differences in target difficulty could otherwise be mistaken for feature effects.
