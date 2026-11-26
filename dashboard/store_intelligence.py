import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from dashboard import api_client
from dashboard.business_reports import report_downloads
from dashboard.catalog_widgets import (
    select_product_scope, select_state_scope, select_store_scope, store_options,
)
from dashboard.product_intelligence import _load
from dashboard.sales_intelligence import _controls

_MODES = (
    "Store rankings", "Store drill-down", "Compare stores", "States",
    "Categories and departments", "Demand matrix",
)
_SORTS = {
    "Highest total demand": "top", "Lowest total demand": "bottom",
    "Fastest-growing": "growth", "Fastest-declining": "decline",
    "Highest average daily demand": "average",
}
_MATRICES = {
    "Store × category": "store_category", "Store × department": "store_department",
    "State × category": "state_category",
}
_METRICS = {
    "Units sold": "total_demand", "Share within store or state (%)": "contribution_pct",
    "Demand growth (%)": "percentage_growth",
}
_COMPARISON_METRICS = {
    "Current units sold": "total_demand", "Previous units sold": "previous_demand",
    "Demand growth (%)": "percentage_growth", "Units per calendar day": "average_daily_demand",
    "Observed products": "observed_products", "Positive-demand products": "positive_demand_products",
}
_RESULT_KEY = "store_intelligence_result"


def _store_basket(state):
    stores = store_options(state)
    key = "sci_store_basket"
    old = st.session_state.get(key, [])
    available = [store for store in old if store in stores]
    if available != old:
        st.session_state[key] = available
    return tuple(st.multiselect(
        "Stores to compare", list(stores), key=key, max_selections=5,
        format_func=stores.__getitem__, placeholder="Choose up to five store codes",
    ))


def _matrix_chart(rows):
    metric = st.selectbox("Heatmap metric", list(_METRICS), key="sci_matrix_metric")
    field = _METRICS[metric]
    values = pd.DataFrame(rows).pivot(index="geography_label", columns="merchandise_label", values=field)
    if values.isna().all().all():
        st.info("No cells have a defined value for this metric.")
        return
    colors = {"colorscale": "RdBu", "zmid": 0} if field == "percentage_growth" else {"colorscale": "Blues"}
    chart = go.Figure(go.Heatmap(
        x=values.columns.tolist(), y=values.index.tolist(),
        z=values.astype(object).where(values.notna(), None).values.tolist(),
        hoverongaps=False, colorbar={"title": metric}, **colors,
    ))
    st.plotly_chart(chart, width="stretch")
    st.caption("Blank cells have no observations or an undefined share or growth denominator.")


def _render(result, mode, params):
    st.caption(
        f"Current {result['period_start']} to {result['period_end']} · "
        f"Previous {result['previous_period_start']} to {result['previous_period_end']}"
    )
    if "cells" in result:
        rows = result["cells"]
        if not rows:
            st.info("No demand matrix observations match this scope.")
            return
        _matrix_chart(rows)
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        rows = result["entities"]
        if not rows:
            st.info("No entities match this analysis.")
            return
        if any(
            row["observed_days"] < result["period_days"]
            or row["previous_observed_days"] < result["period_days"] for row in rows
        ):
            st.warning("Coverage is incomplete for at least one entity or period. Missing observations remain blank.")
        entities = pd.DataFrame(rows)
        details = ("store_id", "store_code", "state", "store_count",
                   "observed_stores", "average_demand_per_observed_store", "rank")
        empty_details = [column for column in details if column in entities and entities[column].isna().all()]
        st.dataframe(entities.drop(columns=empty_details), width="stretch", hide_index=True)
        if len(rows) > 1:
            metric = st.selectbox("Compare by", list(_COMPARISON_METRICS), key="sci_compare_metric")
            field = _COMPARISON_METRICS[metric]
            comparable = entities.dropna(subset=[field])
            if comparable.empty:
                st.info("No entities have a defined value for this metric.")
            else:
                st.plotly_chart(px.bar(comparable, x="label", y=field,
                                       labels={"label": "Entity", field: metric}), width="stretch")
        if result["trend"]:
            trend = pd.DataFrame(result["trend"])
            st.plotly_chart(px.line(
                trend.assign(period=pd.to_datetime(trend["period"])), x="period", y="total_demand",
                color="label", markers=True, hover_data=["observed_days", "expected_days"],
                labels={"total_demand": "Units sold", "label": "Entity"},
            ), width="stretch")
        if result["composition"]:
            composition = pd.DataFrame(result["composition"])
            st.subheader("Category composition")
            st.plotly_chart(px.bar(
                composition, x="group_label", y="total_demand", color="category_label",
                hover_data=["contribution_pct"],
                labels={"total_demand": "Units sold", "group_label": "Entity", "category_label": "Category"},
            ), width="stretch")
    report_downloads(f"Store & Category Intelligence — {mode}", result, params, (
        "Demand measures units sold. Missing observations remain blank.",
        "Growth uses adjacent equal-length windows and requires a nonzero previous total.",
        "Matrix share uses all merchandise demand in each geography within the selected filters.",
    ))


def show_store_intelligence():
    st.title("Store & Category Intelligence")
    mode = st.selectbox("Analysis", _MODES, key="sci_mode")
    params = _controls("sci", show_interval=mode not in ("Store rankings", "Demand matrix"))
    left, right = st.columns(2)
    ready = True
    try:
        with left:
            params["category"], params["department"] = select_product_scope("sci")
        with right:
            if mode == "Compare stores":
                params["state"] = select_state_scope("sci_compare")
                params["store_ids"] = _store_basket(params["state"])
                ready = bool(params["store_ids"])
            else:
                params["state"], params["store_id"] = select_store_scope("sci", placeholder=(
                    "Choose a store code" if mode == "Store drill-down" else "All matching stores"
                ))
                ready = mode != "Store drill-down" or params["store_id"] is not None
    except (requests.RequestException, ValueError):
        st.session_state.pop(_RESULT_KEY, None)
        st.error("Catalog filters could not be loaded from the API.")
        return
    fetch = {
        "Store rankings": api_client.get_store_rankings,
        "Store drill-down": api_client.get_store_performance,
        "Compare stores": api_client.get_store_comparison,
        "States": api_client.get_state_performance,
        "Categories and departments": api_client.get_category_performance,
        "Demand matrix": api_client.get_demand_matrix,
    }[mode]
    if mode == "Store rankings":
        params["sort"] = _SORTS[st.selectbox("Rank stores by", list(_SORTS))]
    elif mode == "Categories and departments":
        params["group_by"] = st.selectbox("Group merchandise by", ["Category", "Department"]).lower()
    elif mode == "Demand matrix":
        params["dimensions"] = _MATRICES[st.selectbox("Matrix dimensions", list(_MATRICES))]
    result = _load(mode, fetch, params, ready=ready, key=_RESULT_KEY, name="store and category")
    if result is not None:
        _render(result, mode, params)
