import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard import api_client
from dashboard.catalog_widgets import _catalog_data, select_product_scope, select_state_scope, store_options


def show_batch_forecast():
    mode = st.selectbox("Forecast scope", [
        "One product across stores", "Selected product-store pairs", "Store", "State",
        "Category", "Department", "Entire business",
    ])
    horizon = st.selectbox("Batch forecast horizon", [7, 14, 28], key="batch_horizon")
    origin = st.date_input("Forecast origin", value=None, key="batch_origin",
                           help="Leave blank to use the latest platform sales date.")
    category, department = select_product_scope("batch")
    state = select_state_scope("batch")
    stores = store_options(state)
    payload = {
        "horizon": horizon, "origin": origin.isoformat() if origin else None,
        "state": state, "category": category, "department": department,
    }
    ready = True
    if mode in ("One product across stores", "Selected product-store pairs"):
        search = st.text_input("Search product codes", key="batch_search")
        page = _catalog_data("products", search=search or None, category=category, department=department,
                             limit=100, offset=0)
        options = {product["product_id"]: product["item_id"] for product in page["products"]}
        st.caption(f"Showing up to 100 of {page['total']} matching products. Search to narrow the list.")
        product = st.selectbox("Product", list(options), index=None, format_func=options.__getitem__,
                               key="batch_product")
        selected_stores = st.multiselect("Stores", list(stores), format_func=stores.__getitem__,
                                         max_selections=100, key="batch_stores")
        ready = product is not None and (bool(selected_stores) or mode == "One product across stores")
        if mode == "Selected product-store pairs":
            scope = (category, department, state)
            if st.session_state.get("batch_pair_scope") != scope:
                st.session_state["batch_pair_scope"] = scope
                st.session_state["batch_pairs"] = []
            if st.button("Add selected pairs", disabled=not ready):
                existing = st.session_state.get("batch_pairs", [])
                additions = [(product, store) for store in selected_stores if (product, store) not in existing]
                st.session_state["batch_pairs"] = (existing + additions)[:100]
            pairs = st.multiselect(
                "Pairs to forecast", st.session_state.get("batch_pairs", []),
                default=st.session_state.get("batch_pairs", []),
                format_func=lambda pair: f"Product {pair[0]} · {stores.get(pair[1], pair[1])}",
                key=f"batch_pair_selection_{len(st.session_state.get('batch_pairs', []))}",
            )
            st.session_state["batch_pairs"] = pairs
            ready = bool(pairs)
            payload.update(scope="pairs", pairs=[{"product_id": product_id, "store_id": store}
                                                  for product_id, store in pairs])
        else:
            payload.update(scope="product", product_ids=[product] if product else [], store_ids=selected_stores)
    elif mode == "Store":
        store = st.selectbox("Store", list(stores), index=None, format_func=stores.__getitem__)
        ready = store is not None
        payload.update(scope="store", store_ids=[store] if store else [])
    else:
        scope = {"State": "state", "Category": "category", "Department": "department",
                 "Entire business": "business"}[mode]
        payload["scope"] = scope
        ready = scope == "business" or payload[scope] is not None
    signature = str(payload)
    if st.session_state.get("batch_signature") != signature:
        st.session_state.pop("batch_preview", None)
        st.session_state.pop("batch_result", None)
        st.session_state["batch_signature"] = signature
    if st.button("Preview forecast scope", disabled=not ready):
        st.session_state.pop("batch_result", None)
        try:
            st.session_state["batch_preview"] = api_client.preview_forecast_scope(payload)
        except requests.RequestException:
            st.session_state.pop("batch_preview", None)
            st.error("Forecast scope could not be resolved.")
    preview = st.session_state.get("batch_preview")
    if preview:
        st.write(f"{preview['candidate_pairs']:,} candidate pairs · {preview['estimated_rows']:,} forecast rows")
        st.caption(f"Limits: {preview['max_pairs']} pairs and {preview['max_rows']} rows.")
        if not preview["within_limits"]:
            st.warning("This scope exceeds synchronous limits. Narrow the filters.")
        if st.button("Generate batch forecast", disabled=not preview["within_limits"] or not preview["candidate_pairs"]):
            st.session_state.pop("batch_result", None)
            try:
                with st.spinner("Loading histories and forecasting…"):
                    st.session_state["batch_result"] = api_client.generate_batch_forecast(payload)
            except requests.HTTPError as error:
                detail = error.response.json().get("detail", "Forecast could not be generated.")
                st.error(detail if isinstance(detail, str) else "Forecast could not be generated.")
            except requests.RequestException:
                st.error("Forecast request failed.")
    result = st.session_state.get("batch_result")
    if result:
        st.metric("Total predicted demand", f"{result['total_prediction']:,.2f}")
        st.write(f"Coverage: {result['coverage']} · {result['eligible_pairs']} eligible of "
                 f"{result['candidate_pairs']} pairs · origin {result['origin']}")
        st.caption(f"Model {result['model_uri']} · version {result['model_version']}")
        if result["exclusions"]:
            st.warning("Some pairs were excluded from this forecast.")
            st.dataframe(pd.DataFrame(result["exclusions"]), hide_index=True)
        historical = pd.DataFrame(result["historical"]).rename(columns={"demand": "units"})
        historical["series"] = "Historical"
        future = pd.DataFrame(result["daily"]).rename(columns={"prediction": "units"})
        future["series"] = "Forecast"
        chart = pd.concat([historical, future], ignore_index=True)
        chart["date"] = pd.to_datetime(chart["date"])
        st.plotly_chart(px.line(chart, x="date", y="units", color="series"), width="stretch")
        st.dataframe(future, hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame(result["breakdowns"]), hide_index=True, width="stretch")
        st.download_button("Download batch forecast CSV", future.to_csv(index=False),
                           file_name="batch_forecast.csv", mime="text/csv")
