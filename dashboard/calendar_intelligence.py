import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard import api_client
from dashboard.business_reports import report_downloads
from dashboard.catalog_widgets import select_product_entry, select_product_scope, select_store_scope
from dashboard.product_intelligence import _load
from dashboard.sales_intelligence import _controls

_RESULT = "calendar_intelligence_result"
_MODES = ("Seasonality", "Calendar events", "Event-relative demand", "SNAP analysis", "Price Intelligence")
_SEASONS = {
    "Day of week": "weekday", "Month of year": "month", "Year": "year",
    "Year and month": "year_month", "Weekday versus weekend": "weekday_weekend",
}
_ASSUMPTIONS = {
    "Seasonality": (
        "Demand is summed by calendar day before daily averages and sample deviation.",
        "Missing dates do not add zero demand. Partial buckets can have fewer eligible days.",
    ),
    "Calendar events": (
        "Each date is counted once within a selection, even when both event slots match.",
        "The non-event baseline is reweighted to the observed weekday mix. Results are associations.",
    ),
    "Event-relative demand": (
        "Offsets are clipped to the requested dates. Nearby centers can share observations across offsets.",
        "The baseline uses non-event weekdays in the same scope. Results are associations.",
    ),
    "SNAP analysis": (
        "Demand is summed by store and date before applying each store’s CA, TX or WI flag.",
        "Means use observed store-days. The differences describe historical associations.",
    ),
    "Price Intelligence": (
        "Weekly quotes match one product and store by the calendar week key. Missing prices remain blank.",
        "Average price is weighted by matched units. Estimated sales value uses matched quotes and units.",
        "Price changes and correlation are descriptive and do not establish causal effects.",
    ),
}


@st.cache_data(ttl=120, show_spinner=False)
def _capabilities():
    return api_client.get_capabilities()


@st.cache_data(ttl=120, show_spinner=False)
def _events():
    return api_client.get_event_catalog()["events"]


def _event_filters(prefix):
    catalog = _events()
    event_types = sorted({event["event_type"] for event in catalog if event["event_type"]})
    kind = st.selectbox("Event type", [None, *event_types], key=f"{prefix}_event_type",
                        format_func=lambda value: value or "All event types")
    names = sorted({
        event["name"] for event in catalog if kind is None or event["event_type"] == kind
    })
    key = f"{prefix}_event_name"
    if st.session_state.get(key) not in names:
        st.session_state.pop(key, None)
    name = st.selectbox("Event name", [None, *names], key=key,
                        format_func=lambda value: value or "All event names")
    with st.expander("Calendar event catalog"):
        st.caption("Occurrence counts cover the calendar, including dates beyond the latest actual sale.")
        _table([entry for entry in catalog if kind is None or entry["event_type"] == kind])
    return {"event_name": name, "event_type": kind}


def _table(rows):
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _chart(rows, x, y, *, color=None, line=False, hover_data=None):
    data = pd.DataFrame(rows)
    if data.empty or data[y].isna().all():
        st.info("No observations support this chart for the selected dates and filters.")
        return
    if x in {"period", "week_start"}:
        data[x] = pd.to_datetime(data[x])
    builder = px.line if line else px.bar
    settings = {"markers": True} if line else {}
    st.plotly_chart(builder(data, x=x, y=y, color=color, hover_data=hover_data, **settings), width="stretch")


def _render(mode, report):
    st.caption(f"{report['period_start']} to {report['period_end']} · {report['period_days']} requested days")
    if mode == "Seasonality":
        buckets = report["buckets"]
        _chart(buckets, "label", "average_daily_demand", hover_data=["observed_days", "expected_days"])
        _table(buckets)
        if any(row["partial_calendar_period"] for row in buckets):
            st.caption("An incomplete month or year is marked as partial.")
        if report["group_by"] in ("month", "year", "year_month") and report["period_days"] < 730:
            st.caption("This window describes historical patterns. Use two or more years of pair history for annual seasonality.")
    elif mode == "Calendar events":
        comparison = report["comparison"]
        _table([{"group": "Selected event dates", **report["event"]},
                {"group": "Non-event baseline", **report["non_event_baseline"]}])
        _chart([
            {"group": "Event weekdays with a baseline", "daily_demand": comparison["matched_average_demand"]},
            {"group": "Weekday-standardized baseline", "daily_demand": comparison["standardized_baseline_average"]},
        ], "group", "daily_demand")
        _table([comparison])
        st.caption(
            "Expected event days count calendar occurrences. A date matching both slots counts once. "
            "The non-event baseline uses the weekday mix of observed event dates."
        )
        if comparison["matched_observed_days"] == 1:
            st.info("The event-associated difference is based on one observed event date.")
    elif mode == "Event-relative demand":
        st.metric("Event dates in the window", report["occurrence_days"])
        rows = [{**point, **point["comparison"]} for point in report["offsets"]]
        rows = [{key: value for key, value in row.items() if key != "comparison"} for row in rows]
        series = [
            {"offset": row["offset"], "series": label, "units_per_day": row[field]}
            for row in rows for label, field in (
                ("All observed demand", "average_daily_demand"),
                ("Matched demand", "matched_average_demand"),
                ("Weekday-standardized baseline", "standardized_baseline_average"),
            )
        ]
        _chart(series, "offset", "units_per_day", color="series", line=True)
        _table(rows)
    elif mode == "SNAP analysis":
        _table(report["groups"])
        _table([{key: report[key] for key in (
            "absolute_difference", "percentage_difference", "excluded_observed_store_days",
        )}])
        _chart(report["trend"], "period", "average_demand_per_observed_store_day", color="status",
               hover_data=["observed_store_days"])
        st.caption("SNAP and non-SNAP means use observed store-days and describe historical associations.")
    else:
        _chart(report["weekly"], "week_start", "unit_price", line=True, hover_data=["observed_days", "expected_days"])
        _chart(report["weekly"], "week_start", "total_demand", hover_data=["observed_days", "expected_days"])
        metrics = {key: value for key, value in report.items() if key not in (
            "weekly", "changes", "period_start", "period_end", "period_days", "latest_sales_date",
            "product_id", "store_id", "_generated_at",
        )}
        _table([metrics])
        if report["changes"]:
            st.subheader("Observed price changes between adjacent weeks")
            _table(report["changes"])
        if report["matched_days"] == 0:
            st.info("No observed sales days matched a usable price in this window.")
        st.caption("Estimated sales value uses matched units and quoted unit prices. Currency is unspecified in the database.")
        st.caption("Price changes and correlation describe historical associations.")


def show_calendar_intelligence():
    st.title("Seasonality & Events")
    mode = st.selectbox("Analysis", _MODES, key="calendar_mode")
    feature = {
        "Calendar events": "events", "Event-relative demand": "events",
        "SNAP analysis": "snap", "Price Intelligence": "pricing",
    }.get(mode)
    try:
        if feature:
            capability = _capabilities()[feature]
            if not capability["available"]:
                st.session_state.pop(_RESULT, None)
                st.info(capability["detail"])
                return
        left, right = st.columns(2)
        with left:
            scope = select_product_scope("calendar")
            use_product = mode == "Price Intelligence" or st.checkbox("Filter by product")
            selection = select_product_entry("calendar", scope) if use_product else None
        with right:
            state, store_id = select_store_scope("calendar")
        product_id = selection[0] if selection else None
        extended = mode == "Seasonality" and product_id and store_id
        params = _controls(
            "calendar", show_interval=mode == "SNAP analysis",
            periods=[30, 60, 90, 180, 365, 730, 1095] if extended else None,
        )
        params.update(category=scope[0], department=scope[1], state=state, store_id=store_id, product_id=product_id)
        ready = not use_product or selection is not None
        if mode == "Seasonality":
            fetch = api_client.get_seasonality
            params["group_by"] = _SEASONS[st.selectbox("Group historical demand by", list(_SEASONS))]
        elif mode in ("Calendar events", "Event-relative demand"):
            fetch = api_client.get_event_analysis if mode == "Calendar events" else api_client.get_event_window
            params.update(_event_filters("calendar"))
            if mode == "Event-relative demand":
                ready = ready and (params["event_name"] is not None or params["event_type"] is not None)
                first, second = st.columns(2)
                params["before"] = first.number_input("Days before", min_value=0, max_value=7, value=3)
                params["after"] = second.number_input("Days after", min_value=0, max_value=7, value=3)
        elif mode == "SNAP analysis":
            fetch = api_client.get_snap_analysis
        else:
            fetch = api_client.get_price_intelligence
            ready = ready and store_id is not None
            if not ready:
                st.info("Select an item code and a store code to compare weekly quotes and demand.")
    except (requests.RequestException, ValueError):
        st.session_state.pop(_RESULT, None)
        st.error("Catalog or calendar metadata could not be loaded from the API.")
        return
    report = _load(mode, fetch, params, ready=ready, key=_RESULT, name="calendar")
    if report is not None:
        _render(mode, report)
        report_downloads(mode, report, params, _ASSUMPTIONS[mode])
