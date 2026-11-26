# DecisionOS V1.2.4 Store & Category Intelligence

Sales Intelligence could show overall growth and separate geographic or merchandise breakdowns. Product Intelligence could compare items. This milestone adds a way to compare stores directly, examine states and merchandise groups, and see which groups contribute to demand in each geography.

## Business hierarchy and filters

A store has a business code such as `CA_1`, a numeric key used by the API, and an optional state. States come from the existing stores table. A product has optional category and department fields. For a category-to-department drill-down, select a category and then choose the **Department** grouping. You can leave department open to see all departments in that category or select one in the catalog. Existing store, state, category, and department filters apply together.

When a recorded sale has null merchandise or state metadata, it remains in the analysis under an Unknown label. Unknown groups count toward totals and shares. A store or state can exist in the catalog without a matching sales record in either window.

## Metrics and denominators

All demand metrics use units sold. The default window is 30 days ending at the last actual sales date for the platform. An explicit historical end date is allowed. The current and previous windows have the same number of days and touch without overlapping. The date anchor stays the same across filters and comparisons.

| Metric | Definition |
|---|---|
| Current and previous demand | Units sold in each window. A window with no matching records returns null. An observed zero remains zero. |
| Absolute change | Current units minus previous units when both were observed. |
| Percentage growth | Absolute change divided by previous units, multiplied by 100. It is null with a missing period or zero baseline. Equal observed nonzero periods return 0%. |
| Average daily demand | Current units divided by the requested number of calendar days. |
| Observed and positive-demand days | Distinct dates with a matching record and distinct dates whose aggregate demand is positive, respectively. |
| Observed and positive-demand products | Distinct product IDs with matching records in the current window and distinct product IDs with a positive current-period sum. |
| State store count | Catalog stores in the geographic scope, alongside the distinct stores with observed sales in that window. |
| Average demand per observed store | State units divided by its observed store count. This is a period total per observed store. Average daily demand is the state's aggregate units per calendar day. |
| Contribution | Entity units divided by all current demand in the filtered scope. A zero denominator returns null. |

For a single-store drill-down, contribution uses all stores matching the state and merchandise filters. For a comparison, it uses only the selected stores that match the filters. Rankings calculate shares before taking the top or bottom rows. Category and department shares include every group within the scope, including null metadata.

Rankings include recorded zero-demand stores and omit stores with no current observations. Growth and decline lists require a strictly positive or negative defined rate, respectively. Zero growth remains valid in performance reports. Ties use ascending store ID. Ranking by average daily demand is equivalent to ranking by total units when all stores use the same calendar-day denominator.

## Backend design and SQL

[store_intelligence_service.py](../../backend/services/store_intelligence_service.py) reuses the optimized date anchor, fact filters, and the existing 25-second statement limit. Parameter values are bound and grouping or ranking expressions come from allowlists.

The entity query reads one fact stream for both periods. PostgreSQL `GROUPING SETS` creates summaries at entity/day and entity/product grain, with entity/store for state counts and entity/category for composition. Day-level sums supply observed days, positive days, growth, and trend buckets. Product-level sums supply distinct assortment and positive-demand counts. Results return only aggregates to Python. The ranking path uses the same query and skips trend and composition work.

Store comparisons accept at most five existing store IDs, using the same calendar bounds and filters for every store. The report derives a date-bucket grid for those stores, including ones with no observations. Weeks begin Monday and months begin on the first day. In-window expected days are counted so boundary buckets may be partial. A bucket with no data has null demand and zero observed days.

The matrix query groups both periods by a geography and merchandise pair. It accepts store/category, store/department, or state/category. It builds the grid from geography and merchandise keys seen in either period. A cross-product cell with no records stays null. A recorded zero stays zero. Each cell's share divides its current units by all current units in that store or state within the filters. Growth uses that same cell's previous-period demand. Geographies and merchandise absent from both periods do not appear in the matrix.

## API and dashboard

[The routes](../../backend/api/routes/store_intelligence.py) and [schemas](../../backend/api/schemas/store_intelligence.py) reuse the analytics error handling, query validation, and request IDs.

| GET endpoint | Purpose |
|---|---|
| `/analytics/store-performance` | Drill into one required `store_id` |
| `/analytics/store-rankings` | Rank by `top`, `bottom`, `growth`, `decline`, or `average` |
| `/analytics/store-comparison` | Compare one to five distinct, repeated `store_ids` |
| `/analytics/state-performance` | Compare states with store and product counts |
| `/analytics/category-performance` | Group by `category` or `department` |
| `/analytics/demand-matrix` | Query `store_category`, `store_department`, or `state_category` |

The [dashboard page](../../dashboard/store_intelligence.py) lets users pick a mode, filters, period, historical end date, and trend interval where relevant. Catalog widgets display store codes and send numeric IDs. **Load store and category analysis** triggers one request for the active mode. Changing report inputs hides stale results. Changing a chart metric uses the loaded response. The heatmap pivots the structured cells and leaves missing or undefined values blank. CSV export combines the loaded sections without another API call.

## Verification and performance

The full safe suite passed **130 tests**, including the prior 109 and a mocked Streamlit walkthrough. Ruff passed. **13 read-only PostgreSQL fixture tests passed**, including the five existing product fixtures. The new fixtures verify daily, weekly, and monthly coverage, growth baselines, ties, distinct assortment, state store counts, department drill-down, and all three matrices. They use synthetic CTE rows. They do not write to PostgreSQL.

```powershell
python -m pytest -q
python -m ruff check src backend dashboard tests
python -m pytest tests/integration -m integration -q
```

Live HTTP checks on the existing API returned HTTP 200 for the following 30-day requests. These are individual measurements rather than latency guarantees.

| Report | Scope and example | Time |
|---|---|---:|
| Store drill-down | CA_1, CA, HOBBIES. 16,032 versus 15,479 units, +3.57%, with 531 positive-demand products out of 565 observed | 18.703 s |
| Store growth ranks | CA, HOBBIES. CA_2 led at +6.71% | 12.152 s |
| Store comparison | CA_1 and CA_2, HOBBIES. CA_1 accounted for 55.99% | 5.984 s |
| State report | CA, HOBBIES. 56,915 versus 55,824 units across four observed stores | 12.950 s |
| Department report | CA_1, HOBBIES. HOBBIES_1 accounted for 92.86% of filtered demand | 4.392 s |
| Store/category matrix | CA_1. FOODS contributed 66.51% and grew 4.65% | 12.820 s |
| Broad state/category matrix | CA × FOODS contained 356,328 units and 64.87% of CA demand | 16.485 s |

Ordinary EXPLAIN showed the indexed anchor lookup and a sequential scan of sales for the broad matrix, plus parallel sales scans for the scoped drill-down and comparison. The drill-down also needs other filtered stores to calculate its denominator. The existing 25-second statement and 30-second client read limits remain in place. Cold-cache performance, longer windows, concurrency, and a live browser walkthrough remain unverified.

For recurring store-scoped workloads, benchmark a candidate `sales(store_id, calendar_id)` index against realistic windows. For repeated broad matrices, consider maintained daily store/category and store/department rollups with observed-record counts. Those rollups would help unit totals and coverage. Exact distinct-product assortment still requires product-level observations or another design that preserves product identity across dates. No schema, index, or migration was applied.

## Files and study order

1. Read the new schemas and routes to understand query validation and response contracts.
2. Read the new service alongside the shared product and sales service helpers. Follow the fact scope, grouped grains, denominators, and matrix grid.
3. Read the new dashboard module and the updated app, catalog widgets, API client, and shared button-driven loader.
4. Read the new unit and integration tests. The read-only PostgreSQL connection fixture is now shared with the existing product integration tests.
5. Review the README and changelog for the milestone summary.

For interviews, explain why a count of distinct products cannot be summed across dates, why a missing heatmap cell differs from an observed zero, how a denominator changes between drill-down and comparison, and why an indexed date anchor alone does not eliminate broad fact scans.
