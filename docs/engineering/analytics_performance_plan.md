# DecisionOS analytics performance plan

## What we measured

The live sales table previously had an estimated 58.3 million rows. The current schema has a composite unique sales index on `(product_id, store_id, calendar_id)`, a unique calendar-date index, and a separate price index for the weekly product-store key. The date anchor uses the sales composite index and has a date-safe fallback.

Representative single live measurements across V1.2 were 20.408 seconds for an unfiltered 30-day product ranking, 16.485 seconds for the broad state/category matrix, and 8.996 seconds for unfiltered 30-day weekday seasonality. In the latest plan, broad seasonality used a sequential sales scan followed by daily aggregation. The 730-day single-pair seasonal report returned in 0.919 seconds. Ordinary EXPLAIN showed the existing sales and price indexes serving the scoped price path. The database statement limit remains 25 seconds and the dashboard read limit remains 30 seconds. These measurements do not establish cold-cache or concurrent performance.

## Evaluate index access first

In a separate staging environment, benchmark a B-tree on `sales(store_id, calendar_id)` for store-first filters, and a B-tree on `sales(calendar_id)` for selective date windows that start from calendar IDs. Compare the plans against the existing composite index and heap access. A BRIN index on `calendar_id` is a lower-storage candidate only if physical row order is correlated with the calendar. Treat index build size, ingestion overhead, and storage as part of the benchmark. No index change is included in V1.2.5.

## Candidate daily rollups

| Grain | Target workloads | Preserve |
|---|---|---|
| Date × store | Executive and store demand, cross-state SNAP, event totals by store | Units, count of source rows, observed store-day presence |
| Date × store × category and date × store × department | Geographic merchandise matrices, scoped contributions and daily trends | Units and source-row counts, including an explicit unknown metadata group |
| Date × product | Platform product trends and rankings without store or state filters | Units and presence so observed zero remains distinct from missing |

Derive state by joining the existing store dimension. Join calendar events and SNAP flags at request time so calendar corrections do not require sales rollup rewrites. A date/category aggregate cannot answer exact distinct assortment across a period by summing daily counts. Keep that metric on a product-preserving path, or benchmark a mergeable distinct-ID representation that preserves exactness. Pair-level sales are already daily. Copying that same grain by itself offers little row reduction.

For scale intuition, a dense 60-day store/category rollup at 10 stores and three known categories contains about 1,800 rows before unknown groups. Broad matrices can then read thousands of rows in place of scanning the sales fact table. Treat that as a row reduction estimate. Measure latency before promising an improvement. Keep weekly prices keyed separately by product, store and week.

## Refresh and rollout

1. In staging, derive rollups for a bounded historical slice from verified facts. Compare sums, distinct scopes, zero versus missing behavior, and event/SNAP results against raw-query fixtures.
2. Refresh complete affected sales dates after ingestion, including dates corrected by late rows. Use a date watermark and an idempotent replacement for those dates. Rebuild affected days when product category or department mappings change.
3. Validate row counts and sales totals per refreshed date. Publish the completed watermark only after all affected aggregates are ready. Keep a raw-query fallback for unsupported filters and unrefreshed dates.
4. Benchmark representative scoped and unfiltered requests over 30, 90 and 365 days with bounded timeouts. Record p50/p95, cold versus warm cache, read I/O, and concurrency separately. Start with ordinary EXPLAIN and reserve execution-heavy diagnostics for controlled staging runs.

This plan proposes changes for later evaluation. V1.2.5 leaves the database schema and ingestion unchanged.
