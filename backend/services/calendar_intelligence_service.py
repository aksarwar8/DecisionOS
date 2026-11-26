from sqlalchemy import text

from backend.services.product_intelligence_service import _scope
from backend.services.sales_intelligence_service import _BUCKETS, read_sales_statement
from src.decisionos.data.extract import get_engine

_EVENT_FIELDS = {"event_name_1", "event_type_1", "event_name_2", "event_type_2"}
_SNAP_FIELDS = {"snap_ca", "snap_tx", "snap_wi"}
_PRICE_FIELDS = {"product_id", "store_id", "wm_yr_wk", "sell_price"}
_SEASONS = {
    "weekday": ("EXTRACT(ISODOW FROM sale_day)", "TO_CHAR(sale_day, 'FMDay')", None),
    "month": ("EXTRACT(MONTH FROM sale_day)", "TO_CHAR(sale_day, 'FMMonth')", "month"),
    "year": ("EXTRACT(YEAR FROM sale_day)", "TO_CHAR(sale_day, 'YYYY')", "year"),
    "year_month": ("date_trunc('month', sale_day)", "TO_CHAR(sale_day, 'YYYY-MM')", "month"),
    "weekday_weekend": (
        "(EXTRACT(ISODOW FROM sale_day) >= 6)::int",
        "CASE WHEN EXTRACT(ISODOW FROM sale_day) >= 6 THEN 'Weekend' ELSE 'Weekday' END", None,
    ),
}
_DAILY_STATISTICS = """
    SUM(demand) AS total_demand, AVG(demand) AS average_daily_demand,
    COUNT(demand) AS observed_days, COUNT(*) AS expected_days,
    COUNT(*) FILTER (WHERE demand > 0) AS positive_demand_days,
    COUNT(*) FILTER (WHERE demand = 0) AS zero_demand_days,
    100.0 * COUNT(demand) / NULLIF(COUNT(*), 0) AS coverage_pct,
    STDDEV_SAMP(demand) AS daily_stddev
"""


class UnsupportedAnalyticsError(RuntimeError):
    """The configured database lacks the metadata required by a report."""


def describe_capabilities(columns):
    calendar = columns.get("calendar", set())
    flags = {
        "events": (
            _EVENT_FIELDS <= calendar,
            "Two calendar event slots are available.",
            "Event analysis requires both calendar event name and type pairs.",
        ),
        "snap": (
            _SNAP_FIELDS <= calendar,
            "State-specific SNAP flags are available for CA, TX and WI.",
            "SNAP analysis requires calendar snap_ca, snap_tx and snap_wi.",
        ),
        "pricing": (
            _PRICE_FIELDS <= columns.get("sell_prices", set()) and "wm_yr_wk" in calendar,
            "Weekly product-store quotes are available in sell_prices.",
            "Price analysis requires sell_prices(product_id, store_id, wm_yr_wk, sell_price) "
            "and the calendar week key.",
        ),
    }
    return {
        name: {"available": available, "detail": supported if available else missing}
        for name, (available, supported, missing) in flags.items()
    }


def get_capabilities():
    query = text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name IN ('calendar', 'sell_prices')
    """)
    with get_engine().connect() as connection:
        columns = {}
        for table, column in connection.execute(query):
            columns.setdefault(table, set()).add(column)
    return describe_capabilities(columns)


def require_capability(feature):
    capability = get_capabilities()[feature]
    if not capability["available"]:
        raise UnsupportedAnalyticsError(capability["detail"])


def _daily_cte(query):
    base, params = _scope(query)
    return base + """,
        daily AS MATERIALIZED (
            SELECT sale_day, SUM(sales_quantity) AS demand FROM facts GROUP BY sale_day
        )
    """, params


def _read(query, statement):
    sql, params = statement
    return read_sales_statement(sql, params, query.days)


def build_seasonality_statement(query):
    base, params = _daily_cte(query)
    key, label, period = _SEASONS[query.group_by]
    partial = "FALSE"
    if period:
        partial = f"""BOOL_OR(
            date_trunc('{period}', sale_day)::date < period_start
            OR (date_trunc('{period}', sale_day) + INTERVAL '1 {period}' - INTERVAL '1 day')::date > period_end
        )"""
    return text(base + f""",
        dated AS (
            SELECT b.*, days.sale_day, d.demand
            FROM bounds b CROSS JOIN LATERAL (
                SELECT b.period_start + n AS sale_day FROM generate_series(0, :days - 1) n
            ) days
            LEFT JOIN daily d ON d.sale_day = days.sale_day
        ), seasonal AS (
            SELECT {key} AS sort_key, {label} AS label, {partial} AS partial_calendar_period,
                   {_DAILY_STATISTICS}
            FROM dated GROUP BY 1, 2
        )
        SELECT b.*, COALESCE((SELECT jsonb_agg(to_jsonb(s) - 'sort_key' ORDER BY sort_key) FROM seasonal s),
                              '[]'::jsonb) AS buckets
        FROM bounds b
    """), params


def get_seasonality(query):
    row, window = _read(query, build_seasonality_statement(query))
    return {**window, "group_by": query.group_by, "buckets": row["buckets"]}


def get_event_catalog():
    require_capability("events")
    sql = text("""
        WITH events AS (
            SELECT slot.name, slot.event_type, COUNT(DISTINCT c.date) AS occurrence_days
            FROM calendar c CROSS JOIN LATERAL (VALUES
                (c.event_name_1, c.event_type_1), (c.event_name_2, c.event_type_2)
            ) slot(name, event_type) WHERE slot.name IS NOT NULL
            GROUP BY slot.name, slot.event_type
        )
        SELECT MIN(date) AS calendar_start, MAX(date) AS calendar_end,
               COALESCE((SELECT jsonb_agg(to_jsonb(e) ORDER BY e.name, e.event_type) FROM events e),
                        '[]'::jsonb) AS events
        FROM calendar
    """)
    with get_engine().connect() as connection:
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        return connection.execute(sql).mappings().one()


def build_event_statement(query, *, relative=False):
    base, params = _daily_cte(query)
    params.update(event_name=query.event_name, event_type=query.event_type)
    base += f""",
        dates AS MATERIALIZED (
            SELECT c.date AS sale_day, d.demand, EXTRACT(ISODOW FROM c.date)::int AS weekday,
                   c.event_name_1 IS NULL AND c.event_name_2 IS NULL AS is_non_event,
                   EXISTS (
                       SELECT 1 FROM (VALUES (c.event_name_1, c.event_type_1),
                                             (c.event_name_2, c.event_type_2)) e(name, event_type)
                       WHERE e.name IS NOT NULL
                       AND (CAST(:event_name AS text) IS NULL OR e.name = :event_name)
                       AND (CAST(:event_type AS text) IS NULL OR e.event_type = :event_type)
                   ) AS is_selected
            FROM calendar c CROSS JOIN bounds b LEFT JOIN daily d ON d.sale_day = c.date
            WHERE c.date BETWEEN b.period_start AND b.period_end
        ), baseline AS (
            SELECT weekday, {_DAILY_STATISTICS} FROM dates WHERE is_non_event GROUP BY weekday
        )
    """
    if relative:
        params.update(before=query.before, after=query.after)
        base += f""",
            offsets AS (
                SELECT offsets.day_offset AS "offset", d.weekday, d.demand
                FROM dates center CROSS JOIN generate_series(
                    -CAST(:before AS integer), CAST(:after AS integer)
                ) offsets(day_offset)
                JOIN dates d ON d.sale_day = center.sale_day + offsets.day_offset
                WHERE center.is_selected
            ), statistics AS (
                SELECT "offset", {_DAILY_STATISTICS} FROM offsets GROUP BY "offset"
            ), weekdays AS (
                SELECT "offset", weekday, COUNT(demand) AS observed_days, SUM(demand) AS total_demand
                FROM offsets GROUP BY "offset", weekday
            )
            SELECT b.*, (SELECT COUNT(*) FROM dates WHERE is_selected) AS occurrence_days,
                   COALESCE((SELECT jsonb_agg(to_jsonb(s)) FROM statistics s), '[]'::jsonb) AS statistics,
                   COALESCE((SELECT jsonb_agg(to_jsonb(w)) FROM weekdays w), '[]'::jsonb) AS weekdays,
                   COALESCE((SELECT jsonb_agg(to_jsonb(n)) FROM baseline n), '[]'::jsonb) AS baseline
            FROM bounds b
        """
    else:
        base += f""",
            selected AS (SELECT * FROM dates WHERE is_selected),
            weekdays AS (
                SELECT weekday, COUNT(demand) AS observed_days, SUM(demand) AS total_demand
                FROM selected GROUP BY weekday
            ), event_summary AS (SELECT {_DAILY_STATISTICS} FROM selected),
            baseline_summary AS (
                SELECT {_DAILY_STATISTICS} FROM dates
                WHERE is_non_event AND weekday IN (SELECT weekday FROM selected)
            )
            SELECT b.*, to_jsonb(e) AS event, to_jsonb(n) AS non_event_baseline,
                   COALESCE((SELECT jsonb_agg(to_jsonb(w)) FROM weekdays w), '[]'::jsonb) AS weekdays,
                   COALESCE((SELECT jsonb_agg(to_jsonb(s)) FROM baseline s), '[]'::jsonb) AS baseline
            FROM bounds b CROSS JOIN event_summary e CROSS JOIN baseline_summary n
        """
    return text(base), params


def mean_difference(current, baseline):
    absolute = current - baseline if current is not None and baseline is not None else None
    return {
        "absolute_difference": absolute,
        "percentage_difference": 100 * absolute / baseline if absolute is not None and baseline else None,
    }


def compare_weekdays(weekdays, baseline):
    """Reweight non-event weekday means by observed event-day composition."""
    lookup = {row["weekday"]: row for row in baseline if row["observed_days"]}
    matched = [row for row in weekdays if row["observed_days"] and row["weekday"] in lookup]
    count = sum(row["observed_days"] for row in matched)
    observed = sum(row["total_demand"] for row in matched) / count if count else None
    adjusted = sum(
        row["observed_days"] * lookup[row["weekday"]]["average_daily_demand"] for row in matched
    ) / count if count else None
    return {
        "matched_observed_days": count,
        "comparable_baseline_days": sum(lookup[row["weekday"]]["observed_days"] for row in matched),
        "matched_average_demand": observed, "standardized_baseline_average": adjusted,
        **mean_difference(observed, adjusted),
    }


def get_event_analysis(query):
    require_capability("events")
    row, window = _read(query, build_event_statement(query))
    return {
        **window, "event_name": query.event_name, "event_type": query.event_type,
        "event": row["event"], "non_event_baseline": row["non_event_baseline"],
        "comparison": compare_weekdays(row["weekdays"], row["baseline"]),
    }


def get_event_window(query):
    require_capability("events")
    row, window = _read(query, build_event_statement(query, relative=True))
    statistics = {point["offset"]: point for point in row["statistics"]}
    empty = dict(
        total_demand=None, average_daily_demand=None, observed_days=0, expected_days=0,
        positive_demand_days=0, zero_demand_days=0, coverage_pct=None, daily_stddev=None,
    )
    return {
        **window, "event_name": query.event_name, "event_type": query.event_type,
        "occurrence_days": row["occurrence_days"],
        "offsets": [
            {
                **statistics.get(offset, empty), "offset": offset,
                "comparison": compare_weekdays(
                    [data for data in row["weekdays"] if data["offset"] == offset], row["baseline"],
                ),
            }
            for offset in range(-query.before, query.after + 1)
        ],
    }


def build_snap_statement(query):
    base, params = _scope(query, metadata=("state",))
    bucket = _BUCKETS[query.aggregation]
    return text(base + f""",
        store_daily AS (
            SELECT sale_day, store_id, state, SUM(sales_quantity) AS demand
            FROM facts GROUP BY sale_day, store_id, state
        ), tagged AS MATERIALIZED (
            SELECT d.*, CASE d.state WHEN 'CA' THEN c.snap_ca
                          WHEN 'TX' THEN c.snap_tx WHEN 'WI' THEN c.snap_wi END AS flag
            FROM store_daily d JOIN calendar c ON c.date = d.sale_day
        ), stats AS (
            SELECT CASE f.flag WHEN 1 THEN 'SNAP' ELSE 'Non-SNAP' END AS status,
                   SUM(t.demand) AS total_demand, COUNT(t.demand) AS observed_store_days,
                   AVG(t.demand) AS average_demand_per_observed_store_day
            FROM (VALUES (1), (0)) f(flag) LEFT JOIN tagged t ON t.flag = f.flag
            GROUP BY f.flag
        ), trend AS (
            SELECT {bucket} AS period, CASE flag WHEN 1 THEN 'SNAP' ELSE 'Non-SNAP' END AS status,
                   SUM(demand) AS total_demand, COUNT(*) AS observed_store_days,
                   AVG(demand) AS average_demand_per_observed_store_day
            FROM tagged WHERE flag IN (0, 1) GROUP BY 1, 2
        )
        SELECT b.*, (SELECT jsonb_agg(to_jsonb(s) ORDER BY status DESC) FROM stats s) AS groups,
               (SELECT COUNT(*) FROM tagged WHERE flag IS NULL OR flag NOT IN (0, 1))
                   AS excluded_observed_store_days,
               COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY period, status) FROM trend t), '[]'::jsonb) AS trend
        FROM bounds b
    """), params


def get_snap_analysis(query):
    require_capability("snap")
    row, window = _read(query, build_snap_statement(query))
    means = {group["status"]: group["average_demand_per_observed_store_day"] for group in row["groups"]}
    return {
        **window, "aggregation": query.aggregation, "groups": row["groups"], "trend": row["trend"],
        "excluded_observed_store_days": row["excluded_observed_store_days"],
        **mean_difference(means["SNAP"], means["Non-SNAP"]),
    }
