
import sys
from pathlib import Path

import requests
import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



from dashboard.api_client import (
    get_model_info,
    get_model_metrics,
    get_model_runs,
    get_model_registry,
    generate_forecast,
    get_product_analytics,
    get_store_analytics,
    get_demand_trends,
)
from dashboard.catalog_widgets import catalog_selection
from dashboard.batch_forecast import show_batch_forecast
from dashboard.calendar_intelligence import show_calendar_intelligence
from dashboard.product_intelligence import show_product_intelligence
from dashboard.sales_intelligence import show_executive_overview, show_sales_intelligence
from dashboard.store_intelligence import show_store_intelligence




def show_sales_period(summary):
    st.caption(
        f"{summary['period_start']} to {summary['period_end']} "
        f"| {summary['period_days']} requested days "
        f"| {summary['positive_sales_days']} with positive sales"
    )


st.set_page_config(
    page_title="DecisionOS",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

st.sidebar.title("DecisionOS")
st.sidebar.caption("Demand Intelligence Platform")

page = st.sidebar.radio(
    "Navigation",
    [
        "Executive Overview",
        "Sales Intelligence",
        "Product Intelligence",
        "Store & Category Intelligence",
        "Seasonality & Events",
        "Demand Forecasting",
        "Product & Store Intelligence",
        "Model Intelligence",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Powered by FastAPI · PostgreSQL · MLflow")


# --------------------------------------------------
# Executive Overview
# --------------------------------------------------


if page == "Executive Overview":
    show_executive_overview()

elif page == "Sales Intelligence":
    show_sales_intelligence()

elif page == "Product Intelligence":
    show_product_intelligence()

elif page == "Store & Category Intelligence":
    show_store_intelligence()

elif page == "Seasonality & Events":
    show_calendar_intelligence()

elif page == "Demand Forecasting":

    st.title("Demand Forecasting")

    forecasting_mode = st.radio("Forecast mode", ["Individual", "Batch and business scope"], horizontal=True)
    if forecasting_mode == "Batch and business scope":
        try:
            show_batch_forecast()
        except requests.RequestException:
            st.error("Catalog information is unavailable.")
        st.stop()

    st.write(
        "Generate future demand predictions using "
        "the DecisionOS hybrid forecasting engine."
    )

    st.divider()
    st.subheader("Forecast Configuration")

    product_id, store_id = catalog_selection("forecast")
    horizon = st.selectbox(
        "Forecast Horizon", options=[7, 14, 28], format_func=lambda x: f"{x} Days",
    )

    forecast_key = (product_id, store_id, horizon)
    if st.session_state.get("forecast_key") != forecast_key:
        st.session_state.pop("forecast_result", None)

    if st.button(
        "Generate Forecast",
        type="primary",
        width="stretch",
        disabled=product_id is None or store_id is None,
    ):

        st.session_state.pop("forecast_result", None)
        with st.spinner("Generating demand forecast..."):

            try:
                result = generate_forecast(
                    product_id=int(product_id),
                    store_id=int(store_id),
                    horizon=int(horizon),
                )

                st.session_state["forecast_result"] = result
                st.session_state["forecast_key"] = forecast_key

            except requests.exceptions.HTTPError as error:
                response = error.response

                try:
                    detail = response.json().get(
                        "detail", response.text
                    )
                except (ValueError, AttributeError):
                    detail = str(error)

                st.error(f"Forecast request failed: {detail}")

            except requests.exceptions.RequestException as error:
                st.error(f"API connection failed: {error}")

            except Exception as error:
                st.error(f"Unexpected error: {error}")

    if "forecast_result" in st.session_state:

        result = st.session_state["forecast_result"]

        forecast_df = pd.DataFrame(result["forecasts"])
        forecast_df["date"] = pd.to_datetime(
            forecast_df["date"]
        )

        if not forecast_df.empty:

            st.divider()
            st.subheader("Forecast Summary")

            total_demand = result["total_predicted_demand"]
            average_demand = total_demand / result["horizon"]

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Total Predicted Demand",
                f"{total_demand:,.2f}",
            )

            col2.metric(
                "Demand per Calendar Day",
                f"{average_demand:,.2f}",
            )

            col3.metric(
                "Forecast Horizon",
                f"{result['horizon']} Days",
            )

            col4.metric(
                "Product / Store",
                f"{result['product_id']} / {result['store_id']}",
            )

            st.divider()
            st.subheader("Daily Demand Forecast")

            fig = px.line(
                forecast_df,
                x="date",
                y="prediction",
                markers=True,
                title=(
                    f"Product {result['product_id']} "
                    f"· Store {result['store_id']}"
                ),
                labels={
                    "date": "Forecast Date",
                    "prediction": "Predicted Demand",
                },
            )

            fig.update_layout(
                template="plotly_dark",
                hovermode="x unified",
            )

            st.plotly_chart(
                fig,
                width="stretch",
            )

            col1, col2 = st.columns(2)

            col1.write(
                f"**Demand Segment:** "
                f"{forecast_df['demand_segment'].iloc[0]}"
            )

            col2.write(
                f"**Selected Model:** "
                f"{forecast_df['selected_model'].iloc[0]}"
            )

            st.divider()
            st.subheader("Forecast Details")

            display_df = forecast_df.copy()
            display_df["date"] = (
                display_df["date"].dt.strftime("%Y-%m-%d")
            )
            display_df["prediction"] = (
                display_df["prediction"].round(4)
            )

            st.dataframe(
                display_df,
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "Download Forecast CSV",
                data=forecast_df.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="decisionos_forecast.csv",
                mime="text/csv",
            )


# --------------------------------------------------
# Product & Store Intelligence
# --------------------------------------------------

elif page == "Product & Store Intelligence":

    st.title("Product & Store Intelligence")

    st.write(
        "Analyze historical demand, product performance "
        "and store-level business activity."
    )

    st.divider()
    st.subheader("Analysis Configuration")

    analysis_product_id, analysis_store_id = catalog_selection("analytics")
    analysis_days = st.selectbox(
        "Historical Period", options=[30, 60, 90, 180, 365], index=2,
        format_func=lambda x: f"{x} Days",
    )

    analytics_key = (analysis_product_id, analysis_store_id, analysis_days)
    if st.session_state.get("analytics_key") != analytics_key:
        st.session_state.pop("analytics_result", None)

    if st.button(
        "Load Business Analytics",
        type="primary",
        width="stretch",
        disabled=analysis_product_id is None or analysis_store_id is None,
    ):

        st.session_state.pop("analytics_result", None)
        with st.spinner("Loading business analytics..."):

            try:
                product_data = get_product_analytics(
                    int(analysis_product_id),
                    int(analysis_days),
                )

                store_data = get_store_analytics(
                    int(analysis_store_id),
                    int(analysis_days),
                )

                trend_data = get_demand_trends(
                    int(analysis_product_id),
                    int(analysis_store_id),
                    int(analysis_days),
                )

                st.session_state["analytics_result"] = {
                    "product": product_data,
                    "store": store_data,
                    "trend": trend_data,
                }
                st.session_state["analytics_key"] = analytics_key

            except requests.exceptions.HTTPError as error:

                response = error.response

                try:
                    detail = response.json().get(
                        "detail", response.text
                    )
                except (ValueError, AttributeError):
                    detail = str(error)

                st.error(f"Analytics request failed: {detail}")

            except requests.exceptions.RequestException as error:
                st.error(f"API connection failed: {error}")

            except Exception as error:
                st.error(f"Unexpected error: {error}")

    if "analytics_result" in st.session_state:

        analytics = st.session_state["analytics_result"]

        product = analytics["product"]
        store = analytics["store"]
        trend = analytics["trend"]

        trend_df = pd.DataFrame(trend["trend"])
        trend_df["date"] = pd.to_datetime(trend_df["date"])

        st.divider()

        # Product intelligence
        st.subheader("Product Intelligence")
        show_sales_period(product)

        st.caption(
            f"{product['item_id']} · "
            f"{product['category']} · "
            f"{product['department']}"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Product Sales",
            f"{product['total_sales']:,.0f}",
        )

        col2.metric(
            "Demand per Calendar Day",
            f"{product['average_daily_demand']:,.2f}",
        )

        col3.metric(
            "Maximum Daily Demand",
            f"{product['maximum_daily_demand']:,.0f}",
        )

        col4.metric(
            "Observed Days",
            product["observed_days"],
        )

        st.divider()

        # Store intelligence
        st.subheader("Store Intelligence")
        show_sales_period(store)

        st.caption(
            f"{store['store_code']} · State: {store['state']}"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Store Sales",
            f"{store['total_sales']:,.0f}",
        )

        col2.metric(
            "Demand per Calendar Day",
            f"{store['average_daily_demand']:,.2f}",
        )

        col3.metric(
            "Maximum Daily Demand",
            f"{store['maximum_daily_demand']:,.0f}",
        )

        col4.metric(
            "Observed Days",
            store["observed_days"],
        )

        st.divider()

        # Historical demand trend
        st.subheader("Historical Demand Trend")
        show_sales_period(trend)

        st.caption(
            f"Product {trend['product_id']} "
            f"at Store {trend['store_id']} "
            f"· Last {trend['days']} days"
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Historical Demand",
            f"{trend['total_demand']:,.0f}",
        )

        col2.metric(
            "Demand per Calendar Day",
            f"{trend['average_daily_demand']:,.2f}",
        )

        col3.metric(
            "Historical Records",
            len(trend_df),
        )

        fig = px.line(
            trend_df,
            x="date",
            y="sales_quantity",
            markers=True,
            title="Daily Historical Sales",
            labels={
                "date": "Date",
                "sales_quantity": "Actual Sales",
            },
        )

        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
        )

        st.plotly_chart(
            fig,
            width="stretch",
        )

        st.divider()

        st.subheader("Historical Sales Data")

        st.dataframe(
            trend_df,
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "Download Historical Sales CSV",
            data=trend_df.to_csv(
                index=False
            ).encode("utf-8"),
            file_name=(
                f"product_{trend['product_id']}_"
                f"store_{trend['store_id']}_history.csv"
            ),
            mime="text/csv",
        )

        st.caption(
            "Note: Product metrics aggregate across all stores, "
            "store metrics aggregate across all products, and "
            "the historical trend represents the selected "
            "product-store combination."
        )


# --------------------------------------------------
# Model Intelligence
# --------------------------------------------------


elif page == "Model Intelligence":

    st.title("Model Intelligence")

    st.write(
        "Monitor forecasting model performance, "
        "experiment history and registered model versions."
    )

    if st.button(
        "Refresh Model Intelligence",
        type="primary",
        width="stretch",
    ):
        st.rerun()

    try:
        # --------------------------------------------------
        # 1. Retrieve model information
        # --------------------------------------------------

        model_info = get_model_info()
        metrics_data = get_model_metrics()
        runs_data = get_model_runs(limit=20)
        registry_data = get_model_registry()

        latest_evaluation = metrics_data.get(
            "latest_evaluation"
        )

        st.divider()

        # --------------------------------------------------
        # 2. Registered model overview
        # --------------------------------------------------

        st.subheader("Registered Model")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Model Name",
            model_info["model_name"],
        )

        col2.metric(
            "Model Version",
            str(model_info["version"]),
        )

        col3.metric(
            "Model Status",
            model_info["status"],
        )

        col4.metric(
            "Active Alias",
            model_info["alias"],
        )

        st.caption(
            f"Model URI: {model_info['model_uri']}"
        )

        st.divider()

        # --------------------------------------------------
        # 3. Latest evaluation metrics
        # --------------------------------------------------

        st.subheader("Latest Model Evaluation")

        if latest_evaluation:

            evaluation_metrics = latest_evaluation.get(
                "metrics", {}
            )

            col1, col2, col3, col4 = st.columns(4)

            mae = evaluation_metrics.get("MAE")
            rmse = evaluation_metrics.get("RMSE")
            wape = evaluation_metrics.get("WAPE")
            evaluated_rows = evaluation_metrics.get(
                "evaluated_rows"
            )

            col1.metric(
                "MAE",
                f"{mae:,.4f}" if mae is not None else "N/A",
                help="Mean Absolute Error. Lower is better.",
            )

            col2.metric(
                "RMSE",
                f"{rmse:,.4f}" if rmse is not None else "N/A",
                help="Root Mean Squared Error. Lower is better.",
            )

            col3.metric(
                "WAPE",
                f"{wape:,.2f}%" if wape is not None else "N/A",
                help="Weighted Absolute Percentage Error. Lower is better.",
            )

            col4.metric(
                "Evaluated Rows",
                f"{evaluated_rows:,.0f}"
                if evaluated_rows is not None
                else "N/A",
            )

            st.caption(
                f"Evaluation Run ID: "
                f"{latest_evaluation['run_id']}"
            )

            st.caption(
                f"Training Run ID: "
                f"{latest_evaluation.get('training_run_id', 'N/A')}"
            )

            st.caption(
                f"Evaluation Time: "
                f"{latest_evaluation.get('start_time', 'N/A')}"
            )

        else:
            st.info(
                metrics_data.get(
                    "message",
                    "No evaluation metrics are available.",
                )
            )

        st.divider()

        # --------------------------------------------------
        # 4. Experiment history
        # --------------------------------------------------

        st.subheader("Experiment History")

        st.caption(
            f"Experiment: {runs_data['experiment_name']}"
        )

        training_runs = runs_data.get(
            "training_runs", []
        )

        evaluation_runs = runs_data.get(
            "evaluation_runs", []
        )

        training_df = pd.DataFrame(training_runs)
        evaluation_df = pd.DataFrame(evaluation_runs)

        tab1, tab2 = st.tabs(
            ["Training Runs", "Evaluation Runs"]
        )

        with tab1:
            if not training_df.empty:

                training_display = training_df[
                    [
                        "run_name",
                        "run_id",
                        "status",
                        "start_time",
                        "metrics",
                    ]
                ].copy()

                st.dataframe(
                    training_display,
                    width="stretch",
                    hide_index=True,
                )

            else:
                st.info("No training runs found.")

        with tab2:
            if not evaluation_df.empty:

                evaluation_display = evaluation_df[
                    [
                        "run_name",
                        "run_id",
                        "status",
                        "start_time",
                        "metrics",
                    ]
                ].copy()

                st.dataframe(
                    evaluation_display,
                    width="stretch",
                    hide_index=True,
                )

            else:
                st.info("No evaluation runs found.")

        st.divider()

        # --------------------------------------------------
        # 5. Model registry
        # --------------------------------------------------

        st.subheader("Model Registry")

        st.write(
            f"Registered Model: **{registry_data['model_name']}**"
        )

        st.write(
            f"Active Version: **{registry_data['active_version']}**"
        )

        st.write(
            f"Active Alias: **{registry_data['active_alias']}**"
        )

        versions = registry_data.get("versions", [])

        if versions:

            versions_df = pd.DataFrame(versions)

            st.dataframe(
                versions_df,
                width="stretch",
                hide_index=True,
            )

        else:
            st.info("No registered model versions found.")

    except requests.exceptions.HTTPError as error:

        try:
            detail = error.response.json().get(
                "detail",
                error.response.text,
            )
        except (ValueError, AttributeError):
            detail = str(error)

        st.error(
            f"Unable to retrieve model intelligence: {detail}"
        )

    except requests.exceptions.RequestException as error:

        st.error(
            f"API connection failed: {error}"
        )

    except Exception as error:

        st.error(
            f"Unexpected error: {error}"
        )
