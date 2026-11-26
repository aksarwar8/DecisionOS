from datetime import timedelta

from sqlalchemy import text

from backend.services.product_intelligence_service import _scope
from backend.services.sales_intelligence_service import _BUCKETS, read_sales_statement

_ENTITY = {"store": "store_id", "state": "state", "category": "category", "department": "department"}
_RANK = {
    "top": ("total_demand DESC", "TRUE"),
    "bottom": ("total_demand ASC", "TRUE"),
    "average": ("average_daily_demand DESC", "TRUE"),
    "growth": ("percentage_growth DESC", "percentage_growth > 0"),
    "decline": ("percentage_growth ASC", "percentage_growth < 0"),
}
_MATRICES = {
    "store_category": ("store_id", "category"),
    "store_department": ("store_id", "department"),
    "state_category": ("state", "category"),
}


def _identities(query, group_by, selected, drill):
    if group_by == "store":
        conditions = []
        if query.state is not None:
            conditions.append("state = :state")
        if drill is not None:
            conditions.append("id = :focus_store")
        elif selected is not None:
            conditions.append("id = ANY(:store_ids)")
        if query.store_id is not None and drill is None:
            conditions.append("id = :store_id")
        where = " AND ".join(conditions) or "TRUE"
        return f"""
            SELECT id AS group_id, store_id AS label, id AS store_id, store_id AS store_code, state
            FROM stores WHERE {where}
        """
    if group_by == "state":
        conditions = []
        if query.state is not None:
            conditions.append("state = :state")
        if query.store_id is not None:
            conditions.append("id = :store_id")
        where = " AND ".join(conditions) or "TRUE"
        return f"""
            SELECT state AS group_id, COALESCE(state, 'Unknown state') AS label, state, COUNT(*) AS store_count
            FROM stores WHERE {where} GROUP BY state
        """
    return f"SELECT group_id, COALESCE(group_id, 'Unknown {group_by}') AS label FROM periods"


def build_entity_statement(query, group_by, *, selected=None, drill=None, ranking=False):
    """One fact stream supplies day coverage, assortment, and optional composition."""
    entity_key = _ENTITY[group_by]
    with_composition = group_by in ("store", "state") and not ranking
    metadata = {entity_key}.intersection({"state", "category", "department"})
    if with_composition:
        metadata.add("category")
    filters = query.model_copy(update={"store_id": None}) if drill is not None else query
    base, params = _scope(filters, comparison=True, store_ids=selected, metadata=sorted(metadata))
    if drill is not None:
        params["focus_store"] = drill
        entity_key = "CASE WHEN store_id = :focus_store THEN store_id END"

    grains = {"sale_day": "day", "product_id": "product"}
    if group_by == "state":
        grains["store_id"] = "store"
    if with_composition:
        grains["category"] = "category"
    dimensions = ", ".join(grains)
    sets = ", ".join(f"(group_id, {column})" for column in grains)
    indicator = " ".join(
        f"WHEN GROUPING({column}) = 0 THEN '{name}'" for column, name in grains.items()
    )
    store_metrics = ""
    if group_by == "state":
        store_metrics = """
            , COALESCE(a.observed_stores, 0) AS observed_stores,
              p.total_demand / NULLIF(a.observed_stores, 0) AS average_demand_per_observed_store
        """
    identities = _identities(query, group_by, selected, drill)
    ctes = base + f"""
        , grouped AS MATERIALIZED (
            SELECT group_id, {dimensions}, CASE {indicator} END AS grain,
                   SUM(sales_quantity) FILTER (WHERE in_current) AS current_demand,
                   SUM(sales_quantity) FILTER (WHERE NOT in_current) AS previous_demand
            FROM (SELECT *, {entity_key} AS group_id FROM facts) scoped
            GROUP BY GROUPING SETS ({sets})
        ), periods AS (
            SELECT group_id, SUM(current_demand) AS total_demand, SUM(previous_demand) AS previous_demand,
                   COUNT(current_demand) AS observed_days, COUNT(previous_demand) AS previous_observed_days,
                   COUNT(*) FILTER (WHERE current_demand > 0) AS positive_demand_days
            FROM grouped WHERE grain = 'day' GROUP BY group_id
        ), assortment AS (
            SELECT group_id,
                   COUNT(current_demand) FILTER (WHERE grain = 'product') AS observed_products,
                   COUNT(*) FILTER (WHERE grain = 'product' AND current_demand > 0) AS positive_demand_products,
                   COUNT(current_demand) FILTER (WHERE grain = 'store') AS observed_stores
            FROM grouped WHERE grain IN ('product', 'store') GROUP BY group_id
        ), scope_total AS (SELECT SUM(total_demand) AS units FROM periods),
        identities AS ({identities}),
        metrics AS (
            SELECT i.*, p.total_demand, p.previous_demand,
                   p.total_demand - p.previous_demand AS absolute_change,
                   100 * (p.total_demand - p.previous_demand) / NULLIF(p.previous_demand, 0) AS percentage_growth,
                   p.total_demand / :days AS average_daily_demand,
                   COALESCE(p.observed_days, 0) AS observed_days,
                   COALESCE(p.previous_observed_days, 0) AS previous_observed_days,
                   COALESCE(p.positive_demand_days, 0) AS positive_demand_days,
                   COALESCE(a.observed_products, 0) AS observed_products,
                   COALESCE(a.positive_demand_products, 0) AS positive_demand_products,
                   100 * p.total_demand / NULLIF(t.units, 0) AS contribution_pct
                   {store_metrics}
            FROM identities i
            LEFT JOIN periods p ON i.group_id IS NOT DISTINCT FROM p.group_id
            LEFT JOIN assortment a ON i.group_id IS NOT DISTINCT FROM a.group_id
            CROSS JOIN scope_total t
        )
    """
    if ranking:
        order, condition = _RANK[query.sort]
        params["limit"] = query.limit
        return text(ctes + f"""
            SELECT b.*, COALESCE((SELECT jsonb_agg(to_jsonb(m) ORDER BY m.rank) FROM (
                SELECT *, ROW_NUMBER() OVER (ORDER BY {order}, group_id) AS rank
                FROM metrics WHERE total_demand IS NOT NULL AND {condition}
                ORDER BY rank LIMIT :limit
            ) m), '[]'::jsonb) AS entities, '[]'::jsonb AS trend, '[]'::jsonb AS composition
            FROM bounds b
        """), params

    bucket = _BUCKETS[query.aggregation]
    composition = "'[]'::jsonb"
    if with_composition:
        composition = """
            COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY c.group_label, c.category_label) FROM (
                SELECT g.group_id, m.label AS group_label, g.category,
                       COALESCE(g.category, 'Unknown category') AS category_label,
                       g.current_demand AS total_demand,
                       100 * g.current_demand::numeric / NULLIF(m.total_demand, 0) AS contribution_pct
                FROM grouped g JOIN metrics m ON g.group_id IS NOT DISTINCT FROM m.group_id
                WHERE g.grain = 'category' AND g.current_demand IS NOT NULL
            ) c), '[]'::jsonb)
        """
    return text(ctes + f"""
        , expected AS (
            SELECT {bucket} AS period, COUNT(*) AS expected_days
            FROM bounds b CROSS JOIN LATERAL (
                SELECT b.period_start + n AS sale_day FROM generate_series(0, :days - 1) n
            ) days GROUP BY 1
        ), actual AS (
            SELECT group_id, {bucket} AS period, SUM(current_demand) AS total_demand, COUNT(*) AS observed_days
            FROM grouped WHERE grain = 'day' AND current_demand IS NOT NULL GROUP BY 1, 2
        ), trend AS (
            SELECT m.group_id, m.label, e.period, a.total_demand,
                   COALESCE(a.observed_days, 0) AS observed_days, e.expected_days
            FROM metrics m CROSS JOIN expected e LEFT JOIN actual a
            ON a.group_id IS NOT DISTINCT FROM m.group_id AND a.period = e.period
        )
        SELECT b.*,
               COALESCE((SELECT jsonb_agg(to_jsonb(m) ORDER BY label, group_id) FROM metrics m), '[]'::jsonb) AS entities,
               COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY label, period, group_id) FROM trend t), '[]'::jsonb) AS trend,
               {composition} AS composition
        FROM bounds b
    """), params


def build_matrix_statement(query):
    geography, merchandise = _MATRICES[query.dimensions]
    metadata = sorted({geography, merchandise} - {"store_id"})
    base, params = _scope(query, comparison=True, metadata=metadata)
    is_store = geography == "store_id"
    geography_label = "st.store_id" if is_store else "COALESCE(g.geography_id, 'Unknown state')"
    store_join = "JOIN stores st ON st.id = g.geography_id" if is_store else ""
    return text(base + f"""
        , totals AS MATERIALIZED (
            SELECT {geography} AS geography_id, {merchandise} AS merchandise_id,
                   SUM(sales_quantity) FILTER (WHERE in_current) AS total_demand,
                   SUM(sales_quantity) FILTER (WHERE NOT in_current) AS previous_demand
            FROM facts GROUP BY 1, 2
        ), geographies AS (
            SELECT geography_id, SUM(total_demand) AS units FROM totals GROUP BY geography_id
        ), merchandise AS (SELECT DISTINCT merchandise_id FROM totals),
        cells AS (
            SELECT g.geography_id, {geography_label} AS geography_label, m.merchandise_id,
                   COALESCE(m.merchandise_id, 'Unknown {merchandise}') AS merchandise_label,
                   t.total_demand, t.previous_demand,
                   100 * t.total_demand::numeric / NULLIF(g.units, 0) AS contribution_pct,
                   100 * (t.total_demand - t.previous_demand)::numeric / NULLIF(t.previous_demand, 0)
                       AS percentage_growth
            FROM geographies g {store_join}
            CROSS JOIN merchandise m LEFT JOIN totals t
            ON t.geography_id IS NOT DISTINCT FROM g.geography_id
            AND t.merchandise_id IS NOT DISTINCT FROM m.merchandise_id
        )
        SELECT b.*, COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY geography_label, merchandise_label)
                              FROM cells c), '[]'::jsonb) AS cells
        FROM bounds b
    """), params


def _read(query, statement):
    sql, params = statement
    row, window = read_sales_statement(sql, params, query.days)
    start = window["period_start"]
    return row, {
        **window, "previous_period_start": start - timedelta(days=query.days),
        "previous_period_end": start - timedelta(days=1),
    }


def get_entity_report(query, group_by, **options):
    row, window = _read(query, build_entity_statement(query, group_by, **options))
    return {
        **window, "group_by": group_by, "aggregation": getattr(query, "aggregation", None),
        "entities": row["entities"], "trend": row["trend"], "composition": row["composition"],
    }


def get_matrix(query):
    row, window = _read(query, build_matrix_statement(query))
    return {**window, "dimensions": query.dimensions, "cells": row["cells"]}
