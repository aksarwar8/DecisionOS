import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard import api_client
from dashboard.business_reports import report_downloads, stamp_report
from dashboard.catalog_widgets import select_product_entry, select_product_scope, select_store_scope
from dashboard.sales_intelligence import _controls

_SORTS = {
    "Top-selling": "top",
    "Bottom-selling": "bottom",
    "Fastest-growing": "growth",
    "Fastest-declining": "decline",
    "Highest variability (CV)": "variability",
    "Highest zero-demand frequency": "zero_frequency",
}
_RESULT_KEY = "product_intelligence_result"
_PAGE_SIZE = 20


def _basket(scope):
    basket_key = "pi_basket"
    scope_key = "pi_basket_scope"
    if st.session_state.get(scope_key) != scope:
        st.session_state[scope_key] = scope
        st.session_state[basket_key] = []
    products = st.session_state[basket_key]
    selection = select_product_entry("pi_compare", scope)
    if st.button("Add product", disabled=(
        selection is None or selection in products or len(products) >= 5
    )):
        products = [*products, selection]
    selected = st.multiselect(
        "Products to compare", products, default=products, format_func=lambda entry: entry[1],
        key=f"pi_compare_basket_{tuple(entry[0] for entry in products)}",
    )
    if selected != products:
        st.session_state[basket_key] = selected
    else:
        st.session_state[basket_key] = products
    return tuple(entry[0] for entry in selected)


def _load(mode, fetch, params, *, ready=True, key=_RESULT_KEY, name="product"):
    signature = (mode, tuple(sorted(params.items())))
    if st.session_state.get(key, (None,))[0] != signature or not ready:
        st.session_state.pop(key, None)
    if st.button(f"Load {name} analysis", type="primary", width="stretch", disabled=not ready):
        st.session_state.pop(key, None)
        with st.spinner("Aggregating historical demand…"):
            try:
                st.session_state[key] = (signature, stamp_report(fetch(**params)))
            except requests.HTTPError as error:
                message = f"{name.capitalize()} analysis could not be loaded."
                if error.response is not None and error.response.status_code in (404, 422, 501, 503):
                    try:
                        detail = error.response.json().get("detail")
                        if isinstance(detail, str):
                            message = detail
                    except ValueError:
                        pass
                st.error(message)
            except (requests.RequestException, ValueError):
                st.error(f"{name.capitalize()} analysis could not be loaded. Check the API and try again.")
    return st.session_state.get(key, (None, None))[1]


def _table(frame):
    st.dataframe(
        frame, width="stretch", hide_index=True,
        column_config={
            "zero_demand_frequency": st.column_config.NumberColumn("Zero-demand frequency", format="percent"),
            "percentage_growth": st.column_config.NumberColumn("Growth (%)", format="%.2f"),
            "contribution_pct": st.column_config.NumberColumn("Contribution (%)", format="%.2f"),
        },
    )


def _render(result, mode, params):
    st.caption(f"{result['period_start']} to {result['period_end']} · {result['period_days']} days")
    products = result["products"]
    product_frame = pd.DataFrame(products)
    if "previous_period_start" in result:
        st.caption(f"Previous period {result['previous_period_start']} to {result['previous_period_end']}")
        if any(row["observed_days"] < result["period_days"]
               or row["previous_observed_days"] < result["period_days"] for row in products):
            st.warning("Coverage is incomplete. Missing observations are excluded from daily statistics.")
    if "total" in result:
        st.caption(f"{result['total']:,} matching results · offset {result['offset']:,}")
    if "summary" in result:
        summary = pd.DataFrame(result["summary"])
        group = "segment" if mode == "Segments" else "classification"
        st.plotly_chart(px.bar(summary, x=group, y="total_demand", labels={"total_demand": "Units sold"}),
                        width="stretch")
        _table(summary)
    if not products:
        st.info("No products match the selected scope and page.")
    else:
        _table(product_frame)
    if result.get("trend"):
        trend = pd.DataFrame(result["trend"])
        codes = {row["product_id"]: row["item_id"] for row in products}
        trend["item_id"] = trend["product_id"].map(codes)
        chart_data = trend.assign(period=pd.to_datetime(trend["period"]))
        st.plotly_chart(
            px.line(chart_data, x="period", y="total_demand", color="item_id", markers=True,
                    hover_data=["observed_days", "expected_days"], labels={"total_demand": "Units sold"}),
            width="stretch",
        )
    if mode == "Volume-based ABC" and products and any(
        row["cumulative_pct"] is not None for row in products
    ):
        chart = px.line(product_frame, x="rank", y="cumulative_pct", markers=True,
                        hover_data=["item_id"], labels={"cumulative_pct": "Cumulative volume share (%)"})
        chart.add_hline(y=80, line_dash="dot")
        chart.add_hline(y=95, line_dash="dot")
        st.plotly_chart(chart, width="stretch")
        st.caption("The curve shows this page at its ranks in the complete filtered catalog.")
    report_downloads(f"Product Intelligence — {mode}", result, params, (
        "Demand measures units sold. Missing observations are excluded from daily statistics.",
        "Zero-demand frequency uses observed days. Growth requires a nonzero previous total.",
        "ABC uses volume share. Ranked and classified tables include the loaded page only.",
    ))


def show_product_intelligence():
    st.title("Product Intelligence")
    mode = st.radio("Analysis", ["Performance", "Rankings", "Segments", "Comparison", "Volume-based ABC"],
                    horizontal=True, key="pi_mode")
    params = _controls("pi", show_interval=mode in ("Performance", "Comparison"))
    left, right = st.columns(2)
    try:
        with left:
            scope = select_product_scope("pi")
        with right:
            params["state"], params["store_id"] = select_store_scope("pi")
        params["category"], params["department"] = scope
        ready = True
        if mode == "Performance":
            fetch = api_client.get_product_performance
            selection = select_product_entry("pi_drill", scope)
            ready = selection is not None
            if selection:
                params["product_id"] = selection[0]
        elif mode == "Comparison":
            fetch = api_client.get_product_comparison
            params["product_ids"] = _basket(scope)
            ready = bool(params["product_ids"])
        else:
            page = st.number_input("Result page", min_value=1, max_value=5_001, step=1,
                                   key=f"pi_page_{mode}")
            params.update(limit=_PAGE_SIZE, offset=(page - 1) * _PAGE_SIZE)
            if mode == "Rankings":
                fetch = api_client.get_product_rankings
                sort = st.selectbox("Rank products by", list(_SORTS))
                params["sort"] = _SORTS[sort]
                if params["sort"] in ("growth", "decline"):
                    params["minimum_previous_demand"] = st.number_input(
                        "Minimum previous units", min_value=1, max_value=2**31 - 1, value=30, step=1,
                    )
            elif mode == "Segments":
                fetch = api_client.get_demand_segments
                params["segment"] = st.selectbox(
                    "Product-store segment", [None, "Zero average", "Low demand", "Medium demand", "High demand"],
                    format_func=lambda value: value or "All segments",
                )
                st.caption("Segments use each product-store pair’s mean units per observed day.")
                if st.checkbox("Filter pairs by product"):
                    selection = select_product_entry("pi_segments", scope)
                    ready = selection is not None
                    if selection:
                        params["product_id"] = selection[0]
            else:
                fetch = api_client.get_abc_analysis
                params["classification"] = st.selectbox(
                    "ABC class", [None, "A", "B", "C", "Unclassified"],
                    format_func=lambda value: value or "All classes",
                )
    except (requests.RequestException, ValueError):
        st.session_state.pop(_RESULT_KEY, None)
        st.error("Catalog filters could not be loaded from the API.")
        return
    result = _load(mode, fetch, params, ready=ready)
    if result is not None:
        _render(result, mode, params)
