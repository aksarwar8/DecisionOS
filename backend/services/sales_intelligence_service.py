from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.api.schemas.sales_intelligence import SalesFilters
from backend.services.analytics_service import AnalyticsNotFoundError, _PLATFORM_LATEST
from src.decisionos.data.extract import get_engine

_DIMENSION_COLUMNS = {
    "day": "sale_day",
    "category": "category",
    "department": "department",
    "store": "store_id",
    "state": "state",
    "product": "product_id",
}
_BUCKETS = {
    "daily": "sale_day",
    "weekly": "date_trunc('week', sale_day)::date",
    "monthly": "date_trunc('month', sale_day)::date",
}
_FILTER_COLUMNS = {
    "store_id": "s.store_id",
    "product_id": "s.product_id",
    "category": "p.category",
    "department": "p.department",
    "state": "st.state",
}


class SalesWindowError(ValueError):
    """The requested historical end date is beyond the latest actual date."""


class SalesQueryTimeout(RuntimeError):
    """PostgreSQL cancelled an analysis at its statement time limit."""


def build_sales_query(filters: SalesFilters, dimensions, *, comparison=False, aggregation=None):
    """Build one bounded aggregate statement from internal SQL fragments."""
    columns = [_DIMENSION_COLUMNS[dimension] for dimension in dimensions]
    select_columns = ", ".join(columns)
    sets = ", ".join(f"({column})" for column in columns)
    indicators = " ".join(
        f"WHEN GROUPING({column}) = 0 THEN '{dimension}'"
        for dimension, column in zip(dimensions, columns)
    )
    params = {"days": filters.days, "end_date": filters.end_date}
    conditions = []
    for field, column in _FILTER_COLUMNS.items():
        value = getattr(filters, field)
        if value is not None:
            conditions.append(f"AND {column} = :{field}")
            params[field] = value
    product_join = (
        "JOIN products p ON p.id = s.product_id"
        if {"category", "department"}.intersection(dimensions)
        or filters.category is not None or filters.department is not None
        else ""
    )
    store_join = (
        "JOIN stores st ON st.id = s.store_id"
        if "state" in dimensions or filters.state is not None else ""
    )
    product_code = "p.item_id" if "product" in dimensions else "NULL::text"
    store_code = "st.store_id" if "store" in dimensions else "NULL::text"
    product_labels = "LEFT JOIN products p ON p.id = g.product_id" if "product" in dimensions else ""
    store_labels = "LEFT JOIN stores st ON st.id = g.store_id" if "store" in dimensions else ""
    first_day = "period_start - :days" if comparison else "period_start"
    trend_rows = "'[]'::jsonb"
    if aggregation is not None:
        bucket = _BUCKETS[aggregation]
        trend_rows = f"""
            COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.period) FROM (
                SELECT {bucket} AS period, SUM(total_demand) AS total_demand,
                       COUNT(*) AS observed_days
                FROM grouped WHERE dimension = 'day' AND sale_day >= b.period_start
                GROUP BY 1
            ) t), '[]'::jsonb)
        """
    return text(f"""
        WITH latest AS MATERIALIZED ({_PLATFORM_LATEST}),
        bounds AS MATERIALIZED (
            SELECT latest_sales_date, period_end, period_end - (:days - 1) AS period_start
            FROM (
                SELECT latest_date AS latest_sales_date,
                       COALESCE(CAST(:end_date AS date), latest_date) AS period_end
                FROM latest
            ) resolved
        ), facts AS (
            SELECT c.date AS sale_day, b.period_start, s.sales_quantity,
                   s.product_id, s.store_id
                   {', p.category, p.department' if product_join else ''}
                   {', st.state' if store_join else ''}
            FROM sales s JOIN calendar c ON c.id = s.calendar_id
            CROSS JOIN bounds b
            {product_join}
            {store_join}
            WHERE b.period_end <= b.latest_sales_date
              AND c.date BETWEEN {first_day} AND b.period_end
              {' '.join(conditions)}
        ), grouped AS MATERIALIZED (
            SELECT CASE {indicators} END AS dimension, {select_columns},
                   SUM(sales_quantity) AS total_demand,
                   SUM(sales_quantity) FILTER (WHERE sale_day >= period_start) AS current_demand,
                   COUNT(*) FILTER (WHERE sale_day >= period_start) AS current_observations
            FROM facts
            GROUP BY GROUPING SETS ({sets})
        )
        SELECT b.*,
               COALESCE((SELECT jsonb_agg(to_jsonb(g) || jsonb_build_object(
                   'product_code', {product_code}, 'store_code', {store_code}))
                   FROM grouped g {product_labels} {store_labels}), '[]'::jsonb) AS groups,
               {trend_rows} AS trend
        FROM bounds b
    """), params


def read_sales_statement(statement, params, days):
    try:
        with get_engine().connect() as connection:
            connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
            result = connection.execute(statement, params).mappings().one()
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "57014":
            raise SalesQueryTimeout from error
        raise
    if result["latest_sales_date"] is None:
        raise AnalyticsNotFoundError("No platform sales data found.")
    if result["period_end"] > result["latest_sales_date"]:
        raise SalesWindowError("End date must be on or before the latest actual sales date.")
    window = {
        key: result[key] for key in ("period_start", "period_end", "latest_sales_date")
    }
    window["period_days"] = days
    return result, window


def _read(filters, dimensions, *, comparison=False, aggregation=None):
    statement, params = build_sales_query(
        filters, dimensions, comparison=comparison, aggregation=aggregation,
    )
    return read_sales_statement(statement, params, filters.days)


def summarize_growth(window, groups):
    start, end, days = window["period_start"], window["period_end"], window["period_days"]
    previous_end = start - timedelta(days=1)
    current = []
    previous = []
    for group in groups:
        if group["dimension"] == "day":
            values = current if group["sale_day"] >= start.isoformat() else previous
            values.append(group["total_demand"])
    current_total = sum(current) if current else None
    previous_total = sum(previous) if previous else None
    change = (
        current_total - previous_total
        if current_total is not None and previous_total is not None else None
    )
    return {
        "current": {
            "start": start, "end": end, "total_demand": current_total,
            "observed_days": len(current), "missing_days": days - len(current),
        },
        "previous": {
            "start": start - timedelta(days=days), "end": previous_end,
            "total_demand": previous_total, "observed_days": len(previous),
            "missing_days": days - len(previous),
        },
        "absolute_change": change,
        "percentage_change": 100 * change / previous_total if change is not None and previous_total else None,
    }


def _observed_groups(groups, dimension):
    return [
        group for group in groups
        if group["dimension"] == dimension and group["current_observations"]
    ]


def summarize_breakdown(groups, dimension):
    key = _DIMENSION_COLUMNS[dimension]
    rows = _observed_groups(groups, dimension)
    total = sum(row["current_demand"] for row in rows)
    rows.sort(key=lambda row: (-row["current_demand"], row[key] is None, str(row[key])))
    return [
        {
            "group_id": row[key],
            "label": (row["store_code"] if dimension == "store" else row[key]) or f"Unknown {dimension}",
            "total_demand": row["current_demand"],
            "percentage_contribution": 100 * row["current_demand"] / total if total else None,
            "observation_count": row["current_observations"],
        }
        for row in rows
    ]


def rank_groups(groups, entity, order, limit):
    key = _DIMENSION_COLUMNS[entity]
    direction = -1 if order == "top" else 1
    rows = _observed_groups(groups, entity)
    rows.sort(key=lambda row: (direction * row["current_demand"], row[key]))
    return [
        {
            "rank": rank, "entity_id": row[key], "code": row[f"{entity}_code"],
            "total_demand": row["current_demand"], "observation_count": row["current_observations"],
        }
        for rank, row in enumerate(rows[:limit], start=1)
    ]


def get_growth(filters):
    result, window = _read(filters, ("day",), comparison=True)
    return {**window, "growth": summarize_growth(window, result["groups"])}


def get_sales_trend(filters, aggregation):
    result, window = _read(filters, ("day",), aggregation=aggregation)
    return {**window, "aggregation": aggregation, "trend": result["trend"]}


def get_breakdown(filters, group_by):
    result, window = _read(filters, (group_by,))
    return {
        **window, "group_by": group_by, "breakdown": summarize_breakdown(result["groups"], group_by),
    }


def get_rankings(filters, entity, order, limit):
    result, window = _read(filters, (entity,))
    return {
        **window, "entity": entity, "order": order,
        "rankings": rank_groups(result["groups"], entity, order, limit),
    }


def get_sales_report(filters, view, aggregation):
    executive = view == "executive"
    breakdowns = ("category",) if executive else ("category", "department", "store", "state")
    dimensions = ("day", *breakdowns, "product", "store") if executive else ("day", *breakdowns)
    result, window = _read(filters, dimensions, comparison=True, aggregation=aggregation)
    groups = result["groups"]
    growth = summarize_growth(window, groups)
    total = growth["current"]["total_demand"]
    return {
        **window, "growth": growth, "aggregation": aggregation, "trend": result["trend"],
        "average_daily_demand": total / filters.days if total is not None else None,
        "active_products": len(_observed_groups(groups, "product")) if executive else None,
        "active_stores": len(_observed_groups(groups, "store")),
        "breakdowns": {dimension: summarize_breakdown(groups, dimension) for dimension in breakdowns},
        "top_products": rank_groups(groups, "product", "top", 5) if executive else [],
        "top_stores": rank_groups(groups, "store", "top", 5) if executive else [],
    }
