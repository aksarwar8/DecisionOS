# V1.3.1 batch and multi-level forecasting

Batch forecasting predicts product-store pairs with the registered hybrid model and sums their predictions to the selected business scope. This is bottom-up aggregation. The same pair forecasts contribute to the daily total and the product, store, category, department and state breakdowns. Individual values are summed without rounding.

## Scope and history

`POST /forecast/scope-preview` resolves catalog combinations for a pair, one product across stores, explicit pairs, one store, a state, a category, a department, or the business. Optional geography and merchandise filters narrow the catalog. It returns the candidate count and estimated horizon rows without touching model inference. Catalog combinations are candidates, including combinations with no recorded sales. Eligibility is unknown until history is read.

`POST /forecast/batch` repeats scope resolution and applies configurable `FORECAST_MAX_PAIRS` and `FORECAST_MAX_ROWS` settings, defaulting to 100 pairs and 2,800 rows. The defaults are conservative guards based on the small live checks below. Full-business inference remains restricted. The preview does not sample the scope.

One query retrieves up to 90 calendar days for all selected pairs. It uses the optimized platform actual-sales anchor unless an earlier origin is supplied. Each pair must end on that common date, contain at least 28 observations, have unique daily keys, continuous dates and finite nonnegative actual sales. Invalid or missing pairs are excluded with reasons. No eligible history produces an error containing the reasons. The response marks a partial forecast when any candidate is excluded. The historical chart begins at the latest start date among included histories so every point represents the same included pairs.

## Forecasting and provenance

[batch_forecast.py](../../src/decisionos/ml/batch_forecast.py) checks aligned origins and passes the histories to the existing hybrid forecaster. Each day, `recursive_forecast` constructs the canonical `FEATURE_COLUMNS` frame for all pairs and calls the model once. It keeps each pair's sales in a separate list and feeds each clipped Random Forest prediction back into its own list. Hybrid selection is applied using the existing historical mean segments. The existing zero-average policy remains intact.

The cached model loader resolves the configured MLflow alias to a version and loads that version. It caches the model and version together, so a response identifies the model actually loaded for the process. Restart the API to pick up an alias change. The scope, exclusions, origin, start and end dates, daily totals, horizon total, model URI and version, timings and breakdowns are returned. The existing individual endpoint remains available.

## Dashboard and verification

The Demand Forecasting page keeps its individual mode and offers batch and business scopes. Catalog controls select products and stores. Preview and generation are explicit actions, and changed inputs clear results. The chart combines history from the included scope with its forecast. The daily table is downloadable as CSV.

Live checks using the registered candidate version 1 returned:

| Scope | End-to-end | History extraction | Inference | Rows | Total units |
|---|---:|---:|---:|---:|---:|
| Product 4, store 1 | 4.761 s | 0.901 s | 0.290 s | 7 | 16.885660 |
| Product 4, stores 1 and 2 | 1.209 s | 0.787 s | 0.320 s | 14 | 38.714870 |
| Pairs 4/1 and 5/2 | 1.128 s | 0.792 s | 0.246 s | 14 | 27.385517 |

The first request includes model initialization. The single-pair batch and existing individual endpoint differed by at most `1.34e-15`. Daily totals summed to each horizon total. A business-wide 28-day preview found 30,490 candidate pairs and 853,720 forecast rows without launching inference.

Synthetic tests exercise batching, independent pair states, common origins, exclusions, coverage and limits. Large-scale latency, browser interaction and throughput beyond these small samples require separate measurement.

Study the request schemas, batch service, recursive and hybrid forecasters, then the dashboard controls and tests. For interviews, explain why a common origin matters, how batching preserves per-series state, and why catalog candidates without observations cannot be treated as zero demand.
