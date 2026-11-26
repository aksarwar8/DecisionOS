# PostgreSQL review

Read-only inspection used the configured DecisionOS connection, a five-second statement timeout, and ordinary `EXPLAIN` with bound parameters. The connection was closed without committing. Planner estimates describe expected work. No query execution timings or exact row counts were collected.

| Table | Estimated live rows | Verified schema and indexes |
|---|---:|---|
| `sales` | 58,330,342 | Integer primary key `id`. Non-null integer foreign keys to product, store and calendar. Non-null integer quantity and nonnegative check. Unique B-tree on `(product_id, store_id, calendar_id)`. Separate nonunique `id` index overlaps the primary key. |
| `calendar` | 1,969 | Integer primary key, non-null date and week key. Unique B-tree on `date`, plus indexes on `id` and `wm_yr_wk`. Includes optional event and SNAP attributes. |
| `products` | 3,049 | Integer primary key, unique business `item_id` index, optional category and department. Additional `id` index. |
| `stores` | 10 | Integer primary key, unique business `store_id` index, optional state. Additional `id` index. |

`prices` was absent from the inspected schema. `extract_prices()` and any diagnostics that call it require a configured prices table. The workspace's `alembic/` contains only Python cache files, with no Alembic source revisions or configuration available. Deployment history and schema migration reproducibility remain unverified.

## Plans and recommendations

Plans were captured for 30-day analytics with product/store ID 1 and 90-day forecast history for the same pair. Product summary used the existing sales unique index with product and calendar constraints. Trend and forecast history used that index for pair lookup, then for individual calendar keys. The calendar date index supported date range filtering and backward lookup of the latest actual sales date.

The store summary and platform overview planned sequential scans over `sales` with hash joins to calendar windows. The overview also planned a sort for distinct aggregates. These plans show where to investigate latency, but provide no measured execution time. The training extractor likewise joins sales to calendar for an inclusive date range and may use a sequential scan for broad windows.

The existing unique index already covers `sales(product_id, store_id, calendar_id)`, and `calendar(date)` already has a unique index. For a separate DBA change, evaluate `sales(store_id, calendar_id)` for selective store windows and `sales(calendar_id)` for selective platform windows and actual-date probes. Both add material storage, ingestion overhead, and build I/O on this table. Test one candidate at a time in a representative staging database before proposing a migration. Leave the overlapping primary-key indexes alone until usage and dependencies have been reviewed.

Candidate SQL for separate review only:

```sql
CREATE INDEX CONCURRENTLY ix_sales_store_calendar ON public.sales (store_id, calendar_id);
CREATE INDEX CONCURRENTLY ix_sales_calendar ON public.sales (calendar_id);
```

## Repeatable read-only checks

Run against the configured DecisionOS database in an existing SQL client. Use the SQL in `backend/services/analytics_service.py` and `src/decisionos/data/extract_forecast.py` with bound parameters to reproduce the exact application plans.

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '2s';
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('calendar', 'sales', 'products', 'stores', 'prices')
ORDER BY table_name, ordinal_position;
SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
WHERE rel.relnamespace = 'public'::regnamespace
  AND rel.relname IN ('calendar', 'sales', 'products', 'stores', 'prices')
ORDER BY 1, 2;
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('calendar', 'sales', 'products', 'stores', 'prices');
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND relname IN ('calendar', 'sales', 'products', 'stores', 'prices');
EXPLAIN SELECT c.date, sum(s.sales_quantity)
FROM public.sales s JOIN public.calendar c ON c.id = s.calendar_id
WHERE s.store_id = 1 AND c.date BETWEEN DATE '2011-04-01' AND DATE '2011-04-30'
GROUP BY c.date;
ROLLBACK;
```

## Live stabilization follow-up

On the original localhost API, product 4, store 1, and the platform overview each exceeded a bounded 32-second probe for a 90-day period. Product and store requests have a 30-second dashboard timeout. The overview uses 60 seconds. The trend returned in 0.117 seconds and MLflow metadata routes returned in 0.012–0.017 seconds.

The original platform anchor probed the trailing calendar dates by `calendar_id` alone, which is the third column in the available sales index. The anchor alone exceeded a seven-second PostgreSQL limit. The revised anchor uses a backward index lookup for each product-store pair when calendar IDs are chronological, then takes the newest of those observations. PostgreSQL checks the ordering before using this path and falls back to the exact joined maximum for a reordered calendar. The revised anchor returned 2016-04-24 in 0.509 seconds.

The overview now materializes the anchor once and uses PostgreSQL grouping sets to aggregate by date, product, and store in one pass. Date totals provide demand and positive-day counts. The product and store groups provide observed entity counts. Read-only PostgreSQL fixtures validated future dates, reordered calendar IDs, empty sales, zero-demand days, and distinct counts. The updated API returned HTTP 200 for product 4 in 0.687 seconds, store 1 in 5.325 seconds, and the overview in 7.272 seconds. These are single measurements against live PostgreSQL from a temporary API process. No dashboard request timeout was changed.

Store and overview plans still scan sales for their totals. Longer periods, cold-cache behavior, and concurrent load were outside this verification. The candidate indexes above remain optional DBA follow-up and were not applied.
