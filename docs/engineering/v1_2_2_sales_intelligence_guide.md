# DecisionOS V1.2.2 sales intelligence guide

V1.2.1 made product and store selection easier. The old overview showed totals for one period, and the existing trend focused on one product-store pair. V1.2.2 lets a user answer broader questions such as whether demand is growing, which categories account for the most units, and which stores or products sold the most. Every demand metric measures units sold.

## Periods and growth

The shared filters in [sales_intelligence.py](../../backend/api/schemas/sales_intelligence.py) default to 30 calendar days. Both dashboard pages offer 30, 60, 90, 180, and 365 days. The API also accepts shorter windows. A blank end date uses the platform's latest actual sales date. An explicit date on or before that date uses the requested value, even if the selected filters have no sales that day. The same platform anchor applies to all filter combinations. The older product-store trend retains its pair-specific anchor.

For `D` days ending on `E`, the current period starts on `E - (D - 1)`. The previous period starts `D` days before that and ends the day before the current period starts. Both include their endpoints. The latest date in the live database was April 24, 2016, so the 30-day windows were March 26–April 24 and February 25–March 25.

`summarize_growth` uses the daily SQL totals to compute absolute change and percentage change. A total of zero means rows were recorded with zero demand. A null total means the filtered period had no observations. Percentage change is null when the previous demand is zero or either total is unavailable. Growth on partial periods uses the recorded totals. The API reports observed and missing dates, and the dashboard shows a coverage warning. One observed date means at least one matching row existed that day. It does not establish that every expected product and store reported.

## Service, filtering, and SQL

[sales_intelligence_service.py](../../backend/services/sales_intelligence_service.py) uses the existing PostgreSQL connection utility and reuses the stabilized anchor from [analytics_service.py](../../backend/services/analytics_service.py). The anchor uses backward lookups on the existing product/store/calendar index when calendar IDs are chronological, with an exact date-based fallback. The new query materializes the anchor and the bounds once per request. Future end dates return 422 and skip the facts scan.

`build_sales_query` binds `days`, `end_date`, and any supplied IDs or metadata filters. It selects grouping columns, joins, and bucket expressions from fixed code mappings. Filter values stay separate from SQL syntax. Multiple filters apply together. Both windows use the same scope. Dimension joins are added only when needed for a filter or grouping.

PostgreSQL reads the end-bounded date range and groups it using `GROUPING SETS`. A report can group the same fact stream into daily totals, category totals, and ranking inputs. Only aggregate rows travel to Python. Growth and bundled views scan the previous period too. Breakdowns and rankings use current-window aggregates. For a standalone endpoint, the service requests only its required grouping.

The daily totals also provide the input for SQL trend buckets. Weeks start on Monday and months use the first calendar day. A boundary week or month can contain fewer days than its calendar size. The label still shows the natural period start. PostgreSQL returns observed buckets in chronological order, including observed zeros. Missing buckets are omitted.

## Contributions and rankings

`summarize_breakdown` divides a group's demand by all demand in the same filtered period. A record whose category, department, or state is null goes into an explicitly labeled unknown group and stays in the denominator. When recorded demand totals zero, contribution percentages are null. Observation counts are counts of sales records.

The ranking query first groups observed rows by numeric product or store ID in PostgreSQL. Business codes are attached after grouping. `rank_groups` sorts the small aggregate result by units sold in the requested direction, breaks ties by ascending numeric ID, and returns at most the requested limit. An observed entity with zero demand is eligible for ranking. An entity without recorded observations in the current period is absent.

## API and dashboard flow

[The route module](../../backend/api/routes/sales_intelligence.py) registers the following GET endpoints. Each uses the same validated window and scope filters.

| Route | Options and output |
|---|---|
| `/analytics/growth` | Current and previous periods, coverage, and changes |
| `/analytics/sales-trend` | `aggregation=daily\|weekly\|monthly` and observed trend buckets |
| `/analytics/breakdown` | `group_by=category\|department\|store\|state` and contribution rows |
| `/analytics/rankings` | `entity=product\|store`, `order=top\|bottom`, and `limit=1..50` |
| `/analytics/sales-report` | `view=executive\|sales` and `aggregation` for a single grouped report |

The schemas define the dates, nullable totals, observed-day counts, grouped rows, and ranked entries. Known cases get useful responses. An absent platform anchor returns 404, a future end date returns 422, and a cancelled statement returns 503 with a suggestion to narrow the search. The existing request ID and generic internal error response still apply.

The [API client](../../dashboard/api_client.py) uses the existing base URL. The dashboard sends one report request when the user clicks Load analysis. The page functions live in [sales_intelligence.py](../../dashboard/sales_intelligence.py). Executive Overview shows the existing core KPIs plus growth, trend, category share, and both top-five rankings. System status and registered model information remain available in an expander. Detailed evaluation metrics and experiment history remain in Model Intelligence.

Sales Intelligence uses the [catalog selectors](../../dashboard/catalog_widgets.py) for state/store and category/department. Changing those filters, the period, the date, or the interval invalidates the displayed result. Switching between the chart's store and state breakdowns uses the loaded report. The download combines comparison periods, growth, trend, and breakdowns in one CSV with a section column. No analytics result cache was added. Users can reload a report with the same button.

The complete flow is browser controls → Streamlit API client → typed FastAPI route → shared window and SQL aggregates → Pydantic response → chart, metric, or CSV.

## Verification and performance

The complete safe suite passed **86 tests**, including the existing 62. Ruff passed. Unit tests use synthetic records and mock the database or service. The suite includes a mocked Streamlit walkthrough covering explicit loading, charts, ranking tables, a CSV download control, chained filters, a geographic view toggle, and stale-result clearing.

Bounded GETs against the existing live API on port 8000 returned HTTP 200. These single timings are representative.

| Live request | Time | Example result |
|---|---:|---|
| `/analytics/growth?days=30&product_id=4&store_id=1` | 0.840 s | 63 current units, 52 previous, +11 units, +21.15% |
| `/analytics/sales-trend?days=30&aggregation=weekly&product_id=4&store_id=1` | 0.784 s | First bucket starts March 21, 2016, with 12 units across two in-window days |
| `/analytics/breakdown?days=30&group_by=category&store_id=1` | 11.181 s | FOODS 92,285 units, 66.51% of filtered demand |
| `/analytics/rankings?days=30&entity=product&product_id=4` | 2.413 s | `HOBBIES_1_004`, 495 units |
| `/analytics/sales-report?days=30&view=executive` | 18.434 s | 1,283,849 versus 1,246,910 units, +2.96% |
| `/analytics/sales-report?days=30&view=sales` | 16.323 s | All four breakdown dimensions for the same platform totals |
| `/analytics/sales-report?days=30&view=sales&state=CA&store_id=1` | 7.160 s | 138,763 current units, 133,448 previous |

Read-only PostgreSQL fixtures exercised the actual SQL for explicit dates, all three buckets, observed zero versus missing days, a null group, and combined filters. Ordinary `EXPLAIN` showed backward index lookups for the anchor and the existing composite index for product-store queries. Store/category and broad reports can still scan the sales table. The backend uses a 25-second statement limit and the client uses a 30-second read limit. Large windows, cold-cache latency, concurrency, and a browser walkthrough against live services remain unverified.

If broader reporting becomes a recurring bottleneck, evaluate the existing proposals for a store/calendar or calendar-only index on representative data. Long historical reports may benefit more from a daily product-store aggregate table or materialized view with observation counts and a defined refresh policy. No schema or index change was applied. [Database review](database_review.md)

## Files and study order

1. Read the new schemas and routes to see validated filters, result types, and error handling.
2. Read the new service to follow the optimized anchor, SQL grouping, growth math, shares, and ranking.
3. Read the modified API client, catalog widgets, and app alongside the new dashboard page module to see how the snapshot is tied to the selected controls.
4. Read the new [tests](../../tests/unit/test_sales_intelligence.py) to see edge cases and the mocked API contract. Router registration was added in [backend/main.py](../../backend/main.py).

For an interview, explain how inclusive and adjacent windows make comparisons reproducible, why missing observations differ from recorded zeros, how grouping sets share a fact scan, how parameter binding differs from an allowlist for SQL identifiers, and why a stable tie-breaker and a consistent share denominator matter. Use the live timing examples to explain why an interactive dashboard issues one grouped report per click.
