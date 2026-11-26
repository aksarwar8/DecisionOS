from sqlalchemy import text

from backend.services.calendar_intelligence_service import require_capability
from backend.services.product_intelligence_service import _scope
from backend.services.sales_intelligence_service import read_sales_statement


def build_price_statement(query):
    base, params = _scope(query)
    filters = [
        f"AND {column} = :{field}"
        for field, column in (("state", "st.state"), ("category", "p.category"), ("department", "p.department"))
        if getattr(query, field) is not None
    ]
    return text(base + f""",
        week_labels AS (
            SELECT wm_yr_wk AS week_key, MIN(date) AS week_start FROM calendar GROUP BY wm_yr_wk
        ), weeks AS (
            SELECT c.wm_yr_wk AS week_key, l.week_start, COUNT(*) AS expected_days
            FROM calendar c JOIN week_labels l ON l.week_key = c.wm_yr_wk CROSS JOIN bounds b
            WHERE c.date BETWEEN b.period_start AND b.period_end AND b.period_end <= b.latest_sales_date
            AND EXISTS (
                SELECT 1 FROM products p CROSS JOIN stores st
                WHERE p.id = :product_id AND st.id = :store_id {' '.join(filters)}
            )
            GROUP BY 1, 2
        ), sales_weeks AS (
            SELECT c.wm_yr_wk AS week_key, SUM(f.sales_quantity) AS total_demand,
                   COUNT(DISTINCT f.sale_day) AS observed_days
            FROM facts f JOIN calendar c ON c.date = f.sale_day GROUP BY 1
        ), distinct_quotes AS (
            SELECT p.wm_yr_wk AS week_key,
                   COUNT(DISTINCT p.sell_price) FILTER (WHERE p.sell_price >= 0
                       AND p.sell_price < 'Infinity'::numeric) AS valid_prices,
                   MIN(p.sell_price) FILTER (WHERE p.sell_price >= 0
                       AND p.sell_price < 'Infinity'::numeric) AS price
            FROM sell_prices p JOIN weeks w ON p.wm_yr_wk = w.week_key
            WHERE p.product_id = :product_id AND p.store_id = :store_id GROUP BY 1
        ), weekly AS MATERIALIZED (
            SELECT w.*, CASE WHEN q.valid_prices = 1 THEN q.price END AS unit_price,
                   COALESCE(q.valid_prices > 1, FALSE) AS price_conflict,
                   s.total_demand, COALESCE(s.observed_days, 0) AS observed_days,
                   s.total_demand::numeric / NULLIF(s.observed_days, 0) AS daily_demand
            FROM weeks w LEFT JOIN sales_weeks s USING (week_key)
            LEFT JOIN distinct_quotes q USING (week_key)
        ), pairs AS (
            SELECT *, LAG(unit_price) OVER ordered AS previous_price,
                   LAG(daily_demand) OVER ordered AS previous_daily,
                   LAG(week_start) OVER ordered AS previous_week
            FROM weekly WINDOW ordered AS (ORDER BY week_start, week_key)
        ), comparable AS (
            SELECT * FROM pairs
            WHERE unit_price IS NOT NULL AND previous_price IS NOT NULL AND week_start - previous_week = 7
        ), changes AS (
            SELECT week_start, previous_price, unit_price AS current_price,
                   previous_daily AS previous_average_daily_demand,
                   daily_demand AS current_average_daily_demand,
                   daily_demand - previous_daily AS average_daily_demand_difference
            FROM comparable WHERE unit_price <> previous_price
        ), summary AS (
            SELECT SUM(total_demand) AS total_demand, COALESCE(SUM(observed_days), 0) AS observed_days,
                   COALESCE(SUM(observed_days) FILTER (WHERE unit_price IS NOT NULL), 0) AS matched_days,
                   SUM(total_demand) FILTER (WHERE unit_price IS NOT NULL) AS matched_demand,
                   SUM(total_demand * unit_price) AS estimated_sales_value,
                   MIN(unit_price) AS minimum_unit_price, MAX(unit_price) AS maximum_unit_price,
                   CASE WHEN MIN(unit_price) FILTER (WHERE daily_demand IS NOT NULL)
                              < MAX(unit_price) FILTER (WHERE daily_demand IS NOT NULL)
                          AND MIN(daily_demand) FILTER (WHERE unit_price IS NOT NULL)
                              < MAX(daily_demand) FILTER (WHERE unit_price IS NOT NULL)
                        THEN CORR(unit_price, daily_demand) END AS price_demand_correlation,
                   COUNT(*) FILTER (WHERE unit_price IS NOT NULL AND daily_demand IS NOT NULL)
                       AS correlation_week_count
            FROM weekly
        )
        SELECT b.*, s.*, 100.0 * matched_days / NULLIF(observed_days, 0) AS match_coverage_pct,
               estimated_sales_value / NULLIF(matched_demand, 0) AS weighted_average_unit_price,
               (SELECT COUNT(*) FROM comparable) AS comparable_price_week_pairs,
               100.0 * (SELECT COUNT(*) FROM changes) / NULLIF((SELECT COUNT(*) FROM comparable), 0)
                   AS price_change_frequency_pct,
               COALESCE((SELECT jsonb_agg(to_jsonb(w) - 'daily_demand' ORDER BY week_start, week_key)
                         FROM weekly w), '[]'::jsonb) AS weekly,
               COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY week_start) FROM changes c), '[]'::jsonb) AS changes
        FROM bounds b CROSS JOIN summary s
    """), params


def get_price_intelligence(query):
    require_capability("pricing")
    statement, params = build_price_statement(query)
    row, window = read_sales_statement(statement, params, query.days)
    return {**row, **window, "product_id": query.product_id, "store_id": query.store_id}
