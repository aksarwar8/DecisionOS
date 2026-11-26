# DecisionOS V1.2.3 Product Intelligence

Product Intelligence helps a retailer investigate which items sell, which have changed, and how reliably demand is observed. It builds on the catalog and Sales Intelligence work. Every demand and ABC calculation uses units sold.

## Period and metrics

Analytics use the latest platform date with actual sales unless the user supplies a valid earlier end date. The current period includes its end date. The previous period has the same duration and ends the day before the current one begins. The dashboard defaults to 30 days and uses the same state/store and category/department catalog filters as Sales Intelligence.

Each product's units are summed across the selected stores for each observed day **before** daily metrics are calculated. If a product sold 2 units in one store and 4 in another on the same day, its demand for that day is 6. The next observed day with zero sales contributes a recorded zero. A date with no matching records is absent from the daily statistics.

| Metric | Definition |
|---|---|
| Total demand and previous demand | Recorded units in each window. A period without observations gets null. |
| Average daily demand | Current units divided by requested calendar days. |
| Average observed-day demand | Current units divided by the number of observed product-days. |
| Absolute demand change and percentage growth | Current minus previous. Percentage divides that change by previous units. Missing totals make both undefined, and a zero baseline makes the percentage undefined. |
| Observed, positive, and zero-demand days | Distinct product-days with any observations, positive aggregated units, or an observed total of zero. |
| Zero-demand frequency | Zero-demand days divided by observed days, returned as a fraction. |
| Standard deviation | Sample standard deviation of observed product-day sums. It is null with fewer than two observations. |
| Coefficient of variation | Sample standard deviation divided by mean observed daily demand. It is null for a zero mean or undefined deviation. |
| Contribution | Product units divided by current units from **all** products in the filter scope. Selecting a smaller comparison basket does not shrink the denominator. A zero or missing scope total makes the percentage undefined. |

A recorded date can still be incomplete across stores. This version counts observed product-days and does not infer whether every expected store reported that day.

## SQL and API

[product_intelligence_service.py](../../backend/services/product_intelligence_service.py) reuses the existing actual-sales-date anchor, filters, bucket expressions, and bounded database execution. The anchor is evaluated once per query. Product metrics first group by product and date, then calculate sums, day counts, and `STDDEV_SAMP` across those daily rows. A comparison query collects all nonselected current demand in a separate group to retain the full contribution denominator without returning unselected products. Historical windows, pagination, and filters are bound parameters. SQL ordering and bucket expressions come from fixed mappings.

[product_intelligence.py in the routes package](../../backend/api/routes/product_intelligence.py) exposes the following GET endpoints, with validation and responses in [the schemas package](../../backend/api/schemas/product_intelligence.py).

| Endpoint | Use |
|---|---|
| `/analytics/product-performance` | Inspect one numeric `product_id`, with metrics and an optional daily, weekly, or monthly trend interval |
| `/analytics/product-comparison` | Compare one to five distinct repeated `product_ids` using the same windows |
| `/analytics/product-rankings` | Sort by `top`, `bottom`, `growth`, `decline`, `variability`, or `zero_frequency` |
| `/analytics/demand-segments` | Count observed product-store pairs and page through them, optionally filtering details by segment or scoping to one product |
| `/analytics/abc-analysis` | Page through volume-based ABC results, optionally filtering details by class |

Comparison buckets use Monday for weeks and the first calendar day for months. Each bucket includes the number of observed and expected dates **inside** the selected window. Missing buckets carry null demand and zero observed days.

Rankings include products with recorded zero demand and exclude products with no current observations. Growth and decline require the previous demand threshold, which defaults to 30 units. Growth requires a positive change and decline requires a negative change. Variability ranks by coefficient of variation and excludes undefined values. All ranking ties use ascending numeric product ID. A page accepts at most 100 rows.

## Demand segments and ABC

The segment thresholds live in [demand_segments.py](../../src/decisionos/ml/demand_segments.py) and are shared by forecasting and SQL analytics. Each **product-store pair** is classified independently using its mean over observed daily sales:

- Zero average equals 0.
- Low demand is greater than 0 through 1.
- Medium demand is greater than 1 through 5.
- High demand is greater than 5.

The dashboard's selected window can differ from the history used by an actual forecast. The model-selection policy and forecasting calculations are unchanged. Segment shares use all pairs in the selected filter scope. Picking a segment filters the detail page while keeping the summary across segments.

ABC uses a SQL window over the complete filtered universe of products with observations, sorted by descending units and ascending product ID. Class is based on the cumulative share **before** each product. Below 80% is A, 80% through just below 95% is B, and 95% or more is C. The item that crosses a threshold stays in the class it started in. When the scope records only zero units, products are Unclassified and both share fields are null. Class filters and pagination run after classification, so changing pages never changes a product's class. This is volume-based ABC analysis.

## Dashboard

[product_intelligence.py in the dashboard](../../dashboard/product_intelligence.py) exposes five views through one mode selector. The catalog search provides item codes for drill-down and for adding up to five items to the comparison basket. The state, store, category and department controls reuse the existing catalog widgets. Each view runs its own analysis only after the user clicks **Load product analysis**. Changes to report inputs clear the old snapshot. Charts and CSV export use the result already returned by the API. The Pareto chart shows cumulative percentages for the displayed page at their ranks in the complete filtered ranking.

## Verification and performance

The default suite passed **109 tests** including the existing 86 and a mocked Streamlit interaction test. Ruff passed. An additional five read-only PostgreSQL integration cases used synthetic CTEs to exercise the actual SQL for daily aggregation, missing observations, growth, variability, contribution, exact forecast segment thresholds, and ABC boundaries. Run these explicitly from the configured project environment.

```powershell
python -m pytest tests/integration/test_product_intelligence_sql.py -m integration -q
```

The existing local API returned HTTP 200 for these representative live requests.

| Analysis | Time | Example |
|---|---:|---|
| Product 4 at store 1 in HOBBIES | 7.051 s | 63 units versus 52, +21.15%, 30% zero-demand days, sample deviation 2.11 units |
| Compare products 4 and 5 at store 1 in HOBBIES | 3.636 s | 63 versus 38 current units for the two items |
| Growth ranking for store 1 and HOBBIES | 3.375 s | `HOBBIES_1_370` ranked first, up 81.08% from 74 to 134 units |
| Segments for product 4 | 0.896 s | Six low, three medium, and one high-demand pair |
| ABC for store 1 and HOBBIES | 3.363 s | 180 A, 162 B, and 223 C products |
| Unfiltered 30-day top ranking | 20.408 s | `FOODS_3_090` ranked first with 17,210 units |

Ordinary EXPLAIN showed the existing product-store-calendar index serving a product-scoped segment query. A broad ranking planned a sequential sales scan and daily hash aggregation. The existing 25-second database statement limit and 30-second dashboard read limit still apply. Broad or long reports can approach the limit. Cold-cache and concurrent performance, longer windows, and a live browser walkthrough remain unverified.

If broad reporting becomes a regular bottleneck, evaluate a maintained daily product-store rollup or partitioned analytical table. Preserve units, observation presence, and date keys so store/state filters and observed-zero semantics survive the rollup. Since the existing sales grain is already daily per pair, a same-grain copy alone saves little. For scale, evaluate partitioning or narrower time-based access alongside a product-day rollup for unfiltered reports. Benchmark any store/calendar or calendar-only index before proposing a migration. No schema changes were applied.

## Study order

1. Read the product schemas and routes to see validation and response contracts.
2. Follow the service from the optimized date anchor to daily grouping, metrics, ranks, and window-based ABC.
3. Compare the shared segmentation thresholds with `hybrid.py`.
4. Follow `dashboard/app.py`, the product page, catalog widgets, and API client to see how item codes become numeric IDs and how results remain tied to inputs.
5. Read the unit tests and integration fixtures to see how missing observations differ from recorded zeros.

Interview topics include choosing the correct aggregation grain, distinguishing requested and observed denominators, handling undefined growth and CV, using SQL window functions for stable classification, and balancing scope accuracy with query latency.
