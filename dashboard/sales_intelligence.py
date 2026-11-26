from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard import api_client
from dashboard.catalog_widgets import select_product_scope, select_store_scope

_PERIODS = [30, 60, 90, 180, 365]


def _report(view, **params):
    key = f"{view}_sales_report"
    selection = tuple(sorted(params.items()))
    if st.session_state.get(key, (None,))[0] != selection:
        st.session_state.pop(key, None)
    if st.button("Load analysis", key=f"{view}_load_report", type="primary", width="stretch"):
        st.session_state.pop(key, None)
        with st.spinner("Aggregating historical sales…"):
            try:
                st.session_state[key] = (selection, api_client.get_sales_report(view=view, **params))
            except (requests.Timeout, requests.ConnectionError):
                st.error("The sales analysis could not reach the API in time. Try again.")
            except requests.HTTPError as error:
                response = error.response
                message = "The sales analysis could not be loaded."
                if response is not None and response.status_code in (404, 422, 503):
                    try:
                        detail = response.json().get("detail")
                        if isinstance(detail, str):
                            message = detail
                    except ValueError:
                        pass
                st.error(message)
            except (requests.RequestException, ValueError):
                st.error("The sales analysis could not be loaded.")
    return st.session_state.get(key, (None, None))[1]


def _controls(prefix, *, show_interval=True):
    columns = st.columns(3 if show_interval else 2)
    period_col, end_col = columns[0], columns[-1]
    with period_col:
        days = st.selectbox("Analysis period", _PERIODS, format_func=lambda value: f"{value} days",
                            key=f"{prefix}_days")
    values = {"days": days}
    if show_interval:
        with columns[1]:
            values["aggregation"] = st.selectbox(
                "Trend interval", ["weekly", "daily", "monthly"],
                format_func=str.title, key=f"{prefix}_interval",
            )
    with end_col:
        end_date = st.date_input(
            "Historical end date", value=None, min_value=date(1900, 1, 1),
            max_value=date.today(), key=f"{prefix}_end_date",
            help="Leave blank to end on the latest date with actual sales.",
        )
    return {**values, "end_date": end_date}


def _number(value, digits=0):
    return "Unavailable" if value is None else f"{value:,.{digits}f}"


def _growth(report):
    growth = report["growth"]
    current, previous = growth["current"], growth["previous"]
    st.caption(
        f"Current {current['start']} to {current['end']} · "
        f"Previous {previous['start']} to {previous['end']}"
    )
    cols = st.columns(3)
    cols[0].metric("Current demand (units)", _number(current["total_demand"]))
    cols[1].metric("Previous demand (units)", _number(previous["total_demand"]))
    percentage = growth["percentage_change"]
    cols[2].metric("Demand growth", "Unavailable" if percentage is None else f"{percentage:+.1f}%")
    if growth["absolute_change"] is not None:
        st.caption(f"Demand change {growth['absolute_change']:+,} units")
    if current["missing_days"] or previous["missing_days"]:
        st.warning(
            f"Observed days: {current['observed_days']}/{report['period_days']} current · "
            f"{previous['observed_days']}/{report['period_days']} previous. "
            "Totals and growth use recorded observations only."
        )
    if current["total_demand"] is None:
        st.info("No sales observations for the current filters and period.")
    if previous["total_demand"] == 0:
        st.info("Percentage growth is undefined when previous demand is zero.")


def _trend(report):
    st.subheader("Historical demand")
    if not report["trend"]:
        st.info("No observed demand to chart.")
        return
    trend = pd.DataFrame(report["trend"])
    trend["period"] = pd.to_datetime(trend["period"])
    chart = px.bar(
        trend, x="period", y="total_demand", hover_data=["observed_days"],
        labels={"period": "Period start", "total_demand": "Units sold", "observed_days": "Observed days"},
    )
    st.plotly_chart(chart, width="stretch")
    if report["aggregation"] != "daily":
        unit = "week (Monday)" if report["aggregation"] == "weekly" else "month"
        st.caption(f"Labels show the start of each {unit}. Boundary periods may be partial.")


def _breakdown(report, dimension):
    st.subheader(f"{dimension.title()} contribution")
    rows = report["breakdowns"][dimension]
    if not rows or rows[0]["percentage_contribution"] is None:
        st.info("No positive demand to calculate contribution shares.")
        return
    chart = px.bar(
        pd.DataFrame(rows), x="label", y="percentage_contribution",
        hover_data=["total_demand", "observation_count"],
        labels={"label": dimension.title(), "percentage_contribution": "Share (%)",
                "total_demand": "Units sold", "observation_count": "Sales records"},
    )
    st.plotly_chart(chart, width="stretch")


def _rankings(rows, title):
    st.subheader(title)
    if not rows:
        st.info("No recorded observations to rank.")
        return
    table = pd.DataFrame(rows)[["rank", "code", "total_demand"]]
    st.dataframe(
        table.rename(columns={"rank": "Rank", "code": "Code", "total_demand": "Units sold"}),
        width="stretch", hide_index=True,
    )


def _download(report):
    records = [
        {"section": "comparison", "label": period, **report["growth"][period]}
        for period in ("current", "previous")
    ]
    records.append({
        "section": "growth",
        "absolute_change": report["growth"]["absolute_change"],
        "percentage_change": report["growth"]["percentage_change"],
    })
    records.extend({"section": "trend", **row} for row in report["trend"])
    for dimension, rows in report["breakdowns"].items():
        records.extend({"section": dimension, **row} for row in rows)
    st.download_button(
        "Download analysis CSV", pd.DataFrame(records).to_csv(index=False),
        file_name=f"decisionos_sales_{report['period_end']}.csv", mime="text/csv",
    )


def _system_status():
    with st.expander("System health and model"):
        st.caption("Open Model Intelligence for evaluation metrics and experiment history.")
        if st.button("Check system status"):
            try:
                st.metric("API status", api_client.get_health()["status"])
            except requests.RequestException:
                st.error("API health could not be checked.")
            try:
                model = api_client.get_model_info()
                st.metric("Registered model", f"{model['status']} · v{model['version']}")
            except requests.RequestException:
                st.error("Registered model information is unavailable.")


def show_executive_overview():
    st.title("Executive Overview")
    report = _report("executive", **_controls("executive"))
    if report is not None:
        _growth(report)
        cols = st.columns(3)
        cols[0].metric("Demand per calendar day", _number(report["average_daily_demand"], 2))
        cols[1].metric("Active products", _number(report["active_products"]))
        cols[2].metric("Active stores", _number(report["active_stores"]))
        _trend(report)
        _breakdown(report, "category")
        left, right = st.columns(2)
        with left:
            _rankings(report["top_products"], "Top five products")
        with right:
            _rankings(report["top_stores"], "Top five stores")
    _system_status()


def show_sales_intelligence():
    st.title("Sales Intelligence")
    params = _controls("sales")
    left, right = st.columns(2)
    try:
        with left:
            params["category"], params["department"] = select_product_scope("sales")
        with right:
            params["state"], params["store_id"] = select_store_scope("sales")
    except (requests.RequestException, ValueError):
        st.session_state.pop("sales_sales_report", None)
        st.error("Sales filters could not be loaded from the catalog.")
        return
    report = _report("sales", **params)
    if report is None:
        return
    _growth(report)
    _trend(report)
    _breakdown(report, "category")
    _breakdown(report, "department")
    geography = st.radio("Geographic breakdown", ["Store", "State"], horizontal=True, key="sales_geography")
    _breakdown(report, geography.lower())
    _download(report)
