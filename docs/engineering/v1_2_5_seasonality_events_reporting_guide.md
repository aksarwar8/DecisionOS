# DecisionOS V1.2.5 Seasonality, Events, Pricing & Reporting

The Seasonality & Events page helps users ask how historical demand varies across dates, which calendar events coincide with demand changes, and whether observed weekly prices and units sold move together. These are descriptive analyses of historical observations.

## Calendar and seasonality

The live calendar has 1,969 dates from January 29, 2011 through June 19, 2016. The latest actual sales date is April 24, 2016. Reports default to that actual-sales anchor and can end earlier. The calendar has 30 event name/type entries across Cultural, National, Religious, and Sporting events. Five dates have both event slots populated. The separate integer flags `snap_ca`, `snap_tx`, and `snap_wi` are each set on 650 dates in the full calendar.

PostgreSQL first sums units across the selected products and stores for each date. It then groups those daily sums by weekday, month of year, year, year and month, or weekday versus weekend. Means and sample standard deviation use observed daily sums. An observed zero counts as a day. A missing day contributes to the expected day count and leaves demand blank. Coverage is observed days divided by expected days. Sample standard deviation requires at least two observations.

Compare average demand and coverage across buckets because months and weekdays can have different numbers of eligible dates. The API marks clipped month or year buckets. Broad scopes permit up to 365 days. A selected product and store permit up to 1,095 days, and the dashboard suggests two or more years of pair history for annual patterns.

## Events and SNAP

Both event slots are searched with a date-level existence check, so a selected date contributes once even if both slots match. Separate reports for overlapping events can include the same date. The event catalog counts distinct calendar dates per name/type and covers the full calendar, including dates after the last actual sale. Historical event analyses restrict dates to the requested sales window.

The event report compares the chosen event dates to dates with neither event slot populated. The baseline uses the same weekdays and is reweighted to the weekday mix of the observed event dates. Weekdays without an observed baseline are excluded from the matched difference. The report shows observed event and baseline counts. A zero baseline permits an absolute difference and leaves the percentage undefined. An unmatched comparison leaves both differences undefined.

Event-relative reports allow zero through seven days on each side. Centers and offset dates stay within the requested window. At each offset, the baseline uses the weekday mix of that offset's observed dates. The same sale date can appear at different offsets when occurrences are close, so offset totals should not be added together.

SNAP first sums demand by **store and date**. Each store uses the flag for its state. The cross-state average is the sum of units divided by observed store-days in each flag group. A day with several observed stores contributes several store-days. Unmapped states and missing or invalid flags are excluded and counted separately. Weekly or monthly trend buckets use the same store-day denominator. Event and SNAP differences describe associations.

## Pricing availability and calculations

The live database has `sell_prices` with an estimated 6.84 million rows. It has a unique `(product_id, store_id, wm_yr_wk)` key, non-null prices, and a nonnegative price check. A read-only sample for product 4 and store 1 found 277 quoted calendar weeks spanning March 5, 2011 to June 19, 2016, with prices from 4.34 to 4.64 and no null quotes in that pair sample. The database stores a numeric quote per item and has no verified currency column.

Pricing requires one product and store. PostgreSQL groups actual sales and quotes at the M5 calendar week key before joining them. Repeated identical quotes collapse to one vote and conflicting valid quotes leave a week unmatched. A missing price remains null. The report includes min/max available quotes and the observed sales days that match a quote. The unit-weighted mean divides matched units times quote by matched units. The matched sum of units times quote is **estimated sales value**, with no assertion about recorded revenue, profit, or margin.

Price-change frequency divides changed adjacent quoted week pairs by all adjacent quoted week pairs. Missing quotes break adjacency. Before/after demand uses each week's observed-day average so partial weeks are comparable by denominator. Pearson correlation uses weeks with both a usable quote and observed demand and is null when either series is constant. Price changes do not identify promotions, and the correlation does not estimate causal elasticity.

A database deployment without the required price relation or keys receives an unavailable state. To enable it later, stage source quotes separately, map source item/store codes to dimension IDs, verify week keys and currency, reject duplicate/conflicting keys and invalid prices, and check coverage before enabling the feature. No ingestion was needed for this milestone.

## API and reporting

| GET endpoint | Purpose |
|---|---|
| `/analytics/capabilities` | Checks the required event, SNAP, and price columns |
| `/analytics/seasonality` | Daily-demand statistics by an allowlisted calendar grouping |
| `/analytics/event-catalog` | Event names, types, occurrence days, and calendar bounds |
| `/analytics/event-analysis` | Event and weekday-matched non-event comparisons |
| `/analytics/event-window` | Demand at each selected offset around event dates |
| `/analytics/snap-analysis` | SNAP versus non-SNAP store-day statistics and trends |
| `/analytics/price-intelligence` | Weekly price, demand, price changes, and estimated matched value |

[The calendar service](../../backend/services/calendar_intelligence_service.py) and [price service](../../backend/services/price_intelligence_service.py) reuse the optimized date anchor, filter bindings, and bounded statement runner. FastAPI [schemas](../../backend/api/schemas/calendar_intelligence.py) validate filters and limits. Unsupported capabilities return a clear message. The Streamlit [page](../../dashboard/calendar_intelligence.py) reuses catalog widgets and the button-driven loader. Changing report inputs hides stale results. Only metadata is cached for two minutes.

[The report formatter](../../dashboard/business_reports.py) exports the loaded executive, sales, product, store/category, seasonality, event, SNAP, and price snapshots. Every report includes a title, UTC generation timestamp, historical dates, applied filters, definitions, and sectioned results. CSV includes all loaded rows. Markdown previews up to 10 rows per section. Paginated exports contain the loaded page. The downloads use the snapshot in session state without another API request.

## Verification

Live HTTP measurements on the existing FastAPI instance:

| Analysis | Time | Example |
|---|---:|---|
| Capabilities and event catalog | 0.327 s / 0.139 s | Events, SNAP and price supported |
| 730-day scoped month-of-year seasonality | 0.919 s | January averaged 2.26 units across 62 observed dates |
| Broad 30-day weekday seasonality | 8.996 s | Monday averaged 39,236.25 units over four observed dates |
| Scoped Easter analysis | 0.916 s | 6 units versus a 3.7-unit weekday-standardized baseline based on one event date |
| Scoped Easter offsets | 4.754 s | 6, 6 and 0 units at offsets −1, 0 and +1 |
| Product 4 SNAP across states | 0.928 s | 1.660 versus 1.685 units per observed store-day, with 300 versus 600 observed store-days |
| Pair pricing, 365 days | 0.999 s | 717 matched units, weighted quote 4.64, estimated sales value 3,326.88 |
| Early pair pricing | 0.875 s | 74 of 109 observed days matched a price |

The default suite passed **149 tests**, including the existing 130 and mocked Streamlit and report generation checks. **19 read-only PostgreSQL fixture tests passed**, including the existing 13. They execute the actual grouping and join statements on synthetic CTEs. Ruff passed.

Broad queries still scan sales. The [performance plan](analytics_performance_plan.md) explains potential optimizations and the existing timeout envelope. A live browser walkthrough, concurrent latency, and full-database price coverage remain unverified. Multi-year windows require one product and store.

## Study order

1. Read the date and query schemas and the calendar service. Follow raw facts → daily sums → seasonal buckets and event baselines.
2. Read the SNAP query and price service to compare store-day and product-store-week grains.
3. Read routes and dashboard controls to see how validation and explicit loading protect the database.
4. Read the report serializer and fixture tests to see deterministic exports and missing-data contracts.

In interviews, explain aggregation grain, why missing demand stays distinct from zero, how weekday standardization controls composition, how unique weekly keys prevent join fanout, and what descriptive price correlation can establish.
