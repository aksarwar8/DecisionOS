from datetime import timedelta

from sqlalchemy import text

from backend.services.analytics_service import _PLATFORM_LATEST
from backend.services.sales_intelligence_service import _BUCKETS, _FILTER_COLUMNS, read_sales_statement
from src.decisionos.ml.demand_segments import DEMAND_SEGMENTS, DEMAND_SEGMENT_UPPER_BOUNDS

_IDENTITY = "p.id AS product_id, p.item_id, p.category, p.department"
_RANK_SORTS = {
    "top": ("total_demand DESC", "TRUE"),
    "bottom": ("total_demand ASC", "TRUE"),
    "growth": ("percentage_growth DESC", "previous_demand >= :minimum AND percentage_growth > 0"),
    "decline": ("percentage_growth ASC", "previous_demand >= :minimum AND percentage_growth < 0"),
    "variability": ("coefficient_of_variation DESC", "coefficient_of_variation IS NOT NULL"),
    "zero_frequency": ("zero_demand_frequency DESC", "TRUE"),
}


def _scope(query, *, comparison=False, product_ids=None):
    params = {"days": query.days, "end_date": query.end_date}
    conditions = []
    for field, column in _FILTER_COLUMNS.items():
        # The comparison basket is separate from the contribution denominator.
        value = None if product_ids is not None and field == "product_id" else getattr(query, field, None)
        if value is not None:
            params[field] = value
            conditions.append(f"AND {column} = :{field}")
    if product_ids is not None:
        params["product_ids"] = product_ids
        conditions.append("AND (c.date >= b.period_start OR s.product_id = ANY(:product_ids))")
    product_join = "JOIN products p ON p.id = s.product_id" if query.category or query.department else ""
    store_join = "JOIN stores st ON st.id = s.store_id" if query.state else ""
    start = "b.period_start - :days" if comparison else "b.period_start"
    return f"""
        WITH latest AS MATERIALIZED ({_PLATFORM_LATEST}),
        bounds AS MATERIALIZED (
            SELECT latest_date AS latest_sales_date, period_end,
                   period_end - (:days - 1) AS period_start
            FROM latest CROSS JOIN LATERAL (
                SELECT COALESCE(CAST(:end_date AS date), latest_date) AS period_end
            ) requested
        ), facts AS (
            SELECT s.product_id, s.store_id, c.date AS sale_day, s.sales_quantity,
                   c.date >= b.period_start AS in_current
            FROM sales s JOIN calendar c ON c.id = s.calendar_id CROSS JOIN bounds b
            {product_join} {store_join}
            WHERE b.period_end <= b.latest_sales_date AND c.date BETWEEN {start} AND b.period_end
            {' '.join(conditions)}
        )
    """, params


def _metrics_sql(selected):
    product_key = (
        "CASE WHEN product_id = ANY(:product_ids) THEN product_id END" if selected else "product_id"
    )
    return f"""
        , daily AS MATERIALIZED (
            SELECT {product_key} AS product_id, sale_day, in_current, SUM(sales_quantity) AS demand
            FROM facts GROUP BY 1, 2, 3
        ), statistics AS (
            SELECT product_id,
                   SUM(demand) FILTER (WHERE in_current) AS total_demand,
                   SUM(demand) FILTER (WHERE NOT in_current) AS previous_demand,
                   COUNT(*) FILTER (WHERE in_current) AS observed_days,
                   COUNT(*) FILTER (WHERE NOT in_current) AS previous_observed_days,
                   COUNT(*) FILTER (WHERE in_current AND demand > 0) AS positive_sales_days,
                   COUNT(*) FILTER (WHERE in_current AND demand = 0) AS zero_demand_days,
                   STDDEV_SAMP(demand) FILTER (WHERE in_current) AS daily_stddev
            FROM daily GROUP BY product_id
        ), denominator AS (SELECT SUM(total_demand) AS total FROM statistics),
        metrics AS (
            SELECT {_IDENTITY}, s.total_demand, s.previous_demand,
                   s.total_demand / :days AS average_daily_demand,
                   s.total_demand / NULLIF(s.observed_days, 0) AS average_observed_day_demand,
                   s.total_demand - s.previous_demand AS absolute_change,
                   100 * (s.total_demand - s.previous_demand) / NULLIF(s.previous_demand, 0) AS percentage_growth,
                   COALESCE(s.observed_days, 0) AS observed_days,
                   COALESCE(s.previous_observed_days, 0) AS previous_observed_days,
                   COALESCE(s.positive_sales_days, 0) AS positive_sales_days,
                   COALESCE(s.zero_demand_days, 0) AS zero_demand_days,
                   s.zero_demand_days::numeric / NULLIF(s.observed_days, 0) AS zero_demand_frequency,
                   s.daily_stddev,
                   s.daily_stddev * s.observed_days / NULLIF(s.total_demand, 0) AS coefficient_of_variation,
                   100 * s.total_demand / NULLIF(d.total, 0) AS contribution_pct
            FROM products p LEFT JOIN statistics s ON s.product_id = p.id CROSS JOIN denominator d
            WHERE {'p.id = ANY(:product_ids)' if selected else 's.observed_days > 0'}
        )
    """


def _detail_statement(query, ids):
    base, params = _scope(query, comparison=True, product_ids=ids)
    scope = ""
    if query.category is not None:
        scope += " AND m.category = :category"
    if query.department is not None:
        scope += " AND m.department = :department"
    bucket = _BUCKETS[query.aggregation]
    return text(base + _metrics_sql(True) + f"""
        , selection AS MATERIALIZED (
            SELECT m.* FROM metrics m JOIN bounds b ON b.period_end <= b.latest_sales_date
            WHERE TRUE {scope}
        ), expected AS (
            SELECT {bucket} AS period, COUNT(*) AS expected_days
            FROM bounds b CROSS JOIN LATERAL (
                SELECT b.period_start + offset_day AS sale_day
                FROM generate_series(0, :days - 1) AS offset_day
            ) calendar_days GROUP BY 1
        ), trend_totals AS (
            SELECT product_id, {bucket} AS period, SUM(demand) AS total_demand, COUNT(*) AS observed_days
            FROM daily WHERE in_current AND product_id IS NOT NULL GROUP BY 1, 2
        ), trend AS (
            SELECT s.product_id, e.period, t.total_demand,
                   COALESCE(t.observed_days, 0) AS observed_days, e.expected_days
            FROM selection s CROSS JOIN expected e LEFT JOIN trend_totals t
            ON t.product_id = s.product_id AND t.period = e.period
        )
        SELECT b.*,
               COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY array_position(:product_ids, s.product_id))
                         FROM selection s), '[]'::jsonb) AS products,
               COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.product_id, t.period)
                         FROM trend t), '[]'::jsonb) AS trend
        FROM bounds b
    """), params


def get_product_comparison(query, ids):
    row, window = _read(query, _detail_statement(query, ids))
    start = window["period_start"]
    return {
        **window, "aggregation": query.aggregation, "products": row["products"], "trend": row["trend"],
        "previous_period_start": start - timedelta(days=query.days),
        "previous_period_end": start - timedelta(days=1),
    }


def _read(query, statement):
    sql, params = statement
    return read_sales_statement(sql, params, query.days)


def _page(query, statement, **extra):
    row, window = _read(query, statement)
    return {
        **window, "products": row["products"], "total": row["total"],
        "limit": query.limit, "offset": query.offset, **extra,
        **({"summary": row["summary"]} if "summary" in row else {}),
    }


def _page_sql(summary=None, *, order="rank"):
    return f"""
        SELECT b.*, (SELECT COUNT(*) FROM eligible) AS total,
               COALESCE((SELECT jsonb_agg(to_jsonb(page) ORDER BY {order}) FROM (
                   SELECT * FROM eligible ORDER BY {order} LIMIT :limit OFFSET :offset
               ) page), '[]'::jsonb) AS products
               {f", ({summary}) AS summary" if summary else ""}
        FROM bounds b
    """


def _ranking_statement(query):
    # The original sales ranking convention sorts quantity, then ascending numeric ID.
    order, condition = _RANK_SORTS[query.sort]
    base, params = _scope(query, comparison=True)
    if query.sort in ("growth", "decline"):
        params["minimum"] = query.minimum_previous_demand
    params.update(limit=query.limit, offset=query.offset)
    return text(base + _metrics_sql(False) + f"""
        , eligible AS MATERIALIZED (
            SELECT *, ROW_NUMBER() OVER (ORDER BY {order}, product_id) AS rank
            FROM metrics WHERE {condition}
        )
    """ + _page_sql()), params


def get_product_rankings(query):
    return _page(
        query, _ranking_statement(query), sort=query.sort,
        minimum_previous_demand=query.minimum_previous_demand,
    )


def _segments_statement(query):
    base, params = _scope(query)
    params.update(
        limit=query.limit, offset=query.offset, segment=query.segment,
        zero=DEMAND_SEGMENT_UPPER_BOUNDS[0], low=DEMAND_SEGMENT_UPPER_BOUNDS[1],
        medium=DEMAND_SEGMENT_UPPER_BOUNDS[2], labels=list(DEMAND_SEGMENTS),
    )
    summary = """
        SELECT jsonb_agg(jsonb_build_object(
            'segment', names.label, 'pair_count', COALESCE(g.pair_count, 0),
            'total_demand', COALESCE(g.total_demand, 0),
            'contribution_pct', 100 * COALESCE(g.total_demand, 0) / NULLIF(t.total, 0)
        ) ORDER BY names.position)
        FROM unnest(CAST(:labels AS text[])) WITH ORDINALITY names(label, position)
        LEFT JOIN grouped g ON g.segment = names.label CROSS JOIN totals t
    """
    return text(base + """
        , pairs AS (
            SELECT product_id, store_id, COUNT(*) AS observed_days, SUM(sales_quantity) AS total_demand,
                   AVG(sales_quantity) AS average_observed_day_demand,
                   CASE WHEN AVG(sales_quantity) <= :zero THEN (CAST(:labels AS text[]))[1]
                        WHEN AVG(sales_quantity) <= :low THEN (CAST(:labels AS text[]))[2]
                        WHEN AVG(sales_quantity) <= :medium THEN (CAST(:labels AS text[]))[3]
                        ELSE (CAST(:labels AS text[]))[4] END AS segment
            FROM facts GROUP BY product_id, store_id
        ), grouped AS (
            SELECT segment, COUNT(*) AS pair_count, SUM(total_demand) AS total_demand
            FROM pairs GROUP BY segment
        ), totals AS (SELECT SUM(total_demand) AS total FROM grouped),
        eligible AS MATERIALIZED (
            SELECT p.product_id, pr.item_id, pr.category, pr.department, p.store_id, st.store_id AS store_code,
                   p.segment, p.total_demand, p.observed_days, p.average_observed_day_demand
            FROM pairs p JOIN products pr ON pr.id = p.product_id JOIN stores st ON st.id = p.store_id
            WHERE CAST(:segment AS text) IS NULL OR p.segment = :segment
        )
    """ + _page_sql(summary, order="total_demand DESC, product_id, store_id")), params


def get_demand_segments(query):
    return _page(query, _segments_statement(query))


def _abc_statement(query):
    base, params = _scope(query)
    params.update(limit=query.limit, offset=query.offset, classification=query.classification)
    summary = """
        SELECT jsonb_agg(jsonb_build_object(
            'classification', names.label, 'product_count', COALESCE(g.product_count, 0),
            'total_demand', COALESCE(g.total_demand, 0),
            'contribution_pct', 100 * COALESCE(g.total_demand, 0) / NULLIF(t.total, 0)
        ) ORDER BY names.position)
        FROM unnest(ARRAY['A', 'B', 'C', 'Unclassified']) WITH ORDINALITY names(label, position)
        LEFT JOIN grouped g ON g.classification = names.label CROSS JOIN totals t
    """
    return text(base + """
        , demand AS (
            SELECT product_id, SUM(sales_quantity) AS total_demand, COUNT(DISTINCT sale_day) AS observed_days
            FROM facts GROUP BY product_id
        ), totals AS (SELECT SUM(total_demand) AS total FROM demand),
        ordered AS (
            SELECT d.*, ROW_NUMBER() OVER volume AS rank, SUM(total_demand) OVER volume AS cumulative
            FROM demand d WINDOW volume AS (ORDER BY total_demand DESC, product_id ROWS UNBOUNDED PRECEDING)
        ), classified AS MATERIALIZED (
            SELECT o.*, 100 * total_demand / NULLIF(t.total, 0) AS contribution_pct,
                   100 * cumulative / NULLIF(t.total, 0) AS cumulative_pct,
                   CASE WHEN t.total = 0 THEN 'Unclassified'
                        WHEN 100 * (cumulative - total_demand) < 80 * t.total THEN 'A'
                        WHEN 100 * (cumulative - total_demand) < 95 * t.total THEN 'B'
                        ELSE 'C' END AS classification
            FROM ordered o CROSS JOIN totals t
        ), grouped AS (
            SELECT classification, COUNT(*) AS product_count, SUM(total_demand) AS total_demand
            FROM classified GROUP BY classification
        ), eligible AS MATERIALIZED (
            SELECT c.product_id, p.item_id, p.category, p.department, c.rank, c.classification,
                   c.total_demand, c.observed_days, c.contribution_pct, c.cumulative_pct
            FROM classified c JOIN products p ON p.id = c.product_id
            WHERE CAST(:classification AS text) IS NULL OR c.classification = :classification
        )
    """ + _page_sql(summary)), params


def get_abc_analysis(query):
    return _page(query, _abc_statement(query))
