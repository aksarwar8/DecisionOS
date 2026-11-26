# Changelog

## 1.2.3

- Added Product Intelligence with product-day metrics, growth and variability rankings, five-product comparison, and CSV exports.
- Exposed historical product-store demand segments using the existing forecasting thresholds.
- Added volume-based ABC analysis with cumulative contribution across the full filtered scope before pagination.

## 1.2.2

- Enhanced Executive Overview with period-over-period demand, category contribution, and top product and store rankings.
- Added Sales Intelligence with catalog filters, selectable trend intervals, contribution charts, and CSV export.
- Added typed analytics endpoints and an on-demand bundled report that reuses the optimized actual-sales anchor.

## 1.2.1

- Added searchable product and store catalog endpoints with metadata filters and stable product pagination.
- Replaced manual ID entry with catalog selectors on the Forecasting and Product & Store Intelligence pages.

## 1.1 stabilization

- Optimized the actual-sales anchor with existing PostgreSQL indexes and consolidated overview aggregation.
- Updated Streamlit layout calls to use the supported width argument.

## 1.1.0

- Explicit canonical feature order and a synthetic training-serving regression test, including the ISO-week rollover.
- Shared validation for complete daily product-store history at training and recursive forecasting boundaries.
- Actual-sales analytics anchors, explicit window bounds and demand denominators, and input-matched dashboard results.
- Shared environment settings, guarded MLflow tracking paths, and UTF-8 Python dependency manifests.
- Standard application logging and request-correlated, safe API error responses.
- Side-effect-free default unit test discovery, guarded manual diagnostics, and a GitHub Actions quality workflow.
- Read-only PostgreSQL schema and planner review, setup documentation, and a V1.1 engineering learning guide.
