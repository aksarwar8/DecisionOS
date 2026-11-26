import logging

import pandas as pd
import mlflow
import mlflow.sklearn

from src.decisionos.config import FORECAST_ARTIFACT_NAME, get_settings
from src.decisionos.data.pipeline import build_sales_dataset
from src.decisionos.ml.dataset import prepare_ml_dataset
from src.decisionos.ml.train import train_random_forest
from src.decisionos.ml.registry import save_model
from src.decisionos.ml.hybrid import (
    hybrid_forecast,
    MODEL_SELECTION,
)


logger = logging.getLogger(__name__)


MIN_HISTORY_DAYS = 56
MIN_SERIES_OBSERVATIONS = 29



def run_forecasting_pipeline(
    history_start_date: str,
    history_end_date: str,
    forecast_start_date: str,
    forecast_end_date: str,
    model_name: str = "decisionos_hybrid_v1.joblib",
) -> dict:

    # --------------------------------------------------
    # 1. Validate date configuration
    # --------------------------------------------------

    history_start = pd.Timestamp(history_start_date)
    history_end = pd.Timestamp(history_end_date)
    forecast_start = pd.Timestamp(forecast_start_date)
    forecast_end = pd.Timestamp(forecast_end_date)

    if history_start > history_end:
        raise ValueError("History start date must precede history end date.")

    if forecast_start > forecast_end:
        raise ValueError("Forecast start date must precede forecast end date.")

    if forecast_start <= history_end:
        raise ValueError("Forecast must start after the historical period.")

    history_days = (history_end - history_start).days + 1

    if history_days < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Insufficient historical window: {history_days} days. "
            f"At least {MIN_HISTORY_DAYS} days are required."
        )

    future_dates = pd.date_range(
        start=forecast_start,
        end=forecast_end,
        freq="D",
    )

    # --------------------------------------------------
    # 2. Configure MLflow
    # --------------------------------------------------

    settings = get_settings()
    tracking_uri = settings.resolve_tracking_uri()
    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_experiment(settings.mlflow_experiment_name)

    logger.info("DECISIONOS FORECASTING PIPELINE")

    # One MLflow run represents one complete pipeline execution.
    with mlflow.start_run(
        run_name=f"hybrid_forecast_{forecast_start.date()}"
    ) as run:

        # --------------------------------------------------
        # 3. Log initial parameters
        # --------------------------------------------------

        mlflow.log_params({
            "model_type": "RandomForestRegressor",
            "forecast_strategy": "Hybrid",
            "history_start_date": str(history_start.date()),
            "history_end_date": str(history_end.date()),
            "forecast_start_date": str(forecast_start.date()),
            "forecast_end_date": str(forecast_end.date()),
            "history_days": history_days,
            "forecast_horizon": len(future_dates),
            "minimum_history_days": MIN_HISTORY_DAYS,
            "n_estimators": 100,
            "max_depth": 15,
            "min_samples_leaf": 2,
            "random_state": 42,
            "demand_segment_policy": str(MODEL_SELECTION),
        })

        # --------------------------------------------------
        # 4. Extract historical sales
        # --------------------------------------------------

        logger.info("\n[1/5] Extracting historical sales...")

        history_df = build_sales_dataset(
            start_date=history_start_date,
            end_date=history_end_date,
        )

        if history_df.empty:
            raise ValueError("No historical sales data was extracted.")

        history_df["date"] = pd.to_datetime(history_df["date"])

        observations = history_df.groupby(
            ["product_id", "store_id"]
        )["date"].nunique()

        minimum_observations = int(observations.min())

        if minimum_observations < MIN_SERIES_OBSERVATIONS:
            raise ValueError(
                "Some product-store series have insufficient history. "
                f"Minimum found: {minimum_observations}; "
                f"required: {MIN_SERIES_OBSERVATIONS}."
            )

        logger.info("Historical dataset shape: %s", history_df.shape)

        # Log dataset information.
        mlflow.log_params({
            "historical_rows": len(history_df),
            "product_store_combinations": len(observations),
            "minimum_series_observations": minimum_observations,
        })

        # --------------------------------------------------
        # 5. Prepare training dataset
        # --------------------------------------------------

        logger.info("\n[2/5] Preparing ML training dataset...")

        train_df = prepare_ml_dataset(history_df)

        if train_df.empty:
            raise ValueError("Training dataset is empty.")

        training_rows = len(train_df)

        logger.info("Training dataset shape: %s", train_df.shape)

        mlflow.log_params({
            "training_rows": training_rows,
            "feature_count": 14,
        })

        # --------------------------------------------------
        # 6. Train Random Forest
        # --------------------------------------------------

        logger.info("\n[3/5] Training Random Forest model...")

        model = train_random_forest(train_df)

        # --------------------------------------------------
        # 7. Save model artifact
        # --------------------------------------------------

        logger.info("\n[4/5] Saving trained model...")

        model_path = save_model(
            model=model,
            model_name=model_name,
        )

        # Also log the model in MLflow's artifact store.
        mlflow.sklearn.log_model(
            sk_model=model,
            name="random_forest_model",
            skops_trusted_types=[
                "sklearn.tree._tree.Tree"
            ],
        )

        # --------------------------------------------------
        # 8. Generate hybrid forecasts
        # --------------------------------------------------

        logger.info("\n[5/5] Generating hybrid forecasts...")

        forecasts = hybrid_forecast(
            model=model,
            history_df=history_df,
            future_dates=future_dates,
        )

        if forecasts.empty:
            raise ValueError("Forecast generation returned no predictions.")

        if forecasts["prediction"].isna().any():
            raise ValueError("Forecast contains missing predictions.")

        if (forecasts["prediction"] < 0).any():
            raise ValueError("Forecast contains negative predictions.")

        # --------------------------------------------------
        # 9. Log forecast output information
        # --------------------------------------------------

        forecast_rows = len(forecasts)

        total_predicted_demand = float(
            forecasts["prediction"].sum()
        )

        mlflow.log_metrics({
            "forecast_rows": forecast_rows,
            "total_predicted_demand": total_predicted_demand,
        })

        # Save forecast output as an MLflow artifact.
        output_dir = settings.project_path(settings.forecast_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        forecast_path = output_dir / FORECAST_ARTIFACT_NAME
        forecasts.to_csv(
            forecast_path,
            index=False,
        )

        mlflow.log_artifact(str(forecast_path))

        # --------------------------------------------------
        # 10. Return pipeline results
        # --------------------------------------------------

        result = {
            "run_id": run.info.run_id,
            "model_path": model_path,
            "training_rows": training_rows,
            "history_days": history_days,
            "history_start_date": history_start,
            "history_end_date": history_end,
            "forecast_start_date": forecast_start,
            "forecast_end_date": forecast_end,
            "forecast_horizon": len(future_dates),
            "forecast_rows": forecast_rows,
            "total_predicted_demand": total_predicted_demand,
            "forecasts": forecasts,
        }

        logger.info("FORECASTING PIPELINE COMPLETED")

        logger.info("MLflow Run ID: %s", run.info.run_id)
        logger.info("Model: %s", model_path)
        logger.info("Training rows: %s", training_rows)
        logger.info("Forecast horizon: %s", len(future_dates))
        logger.info("Forecast rows: %s", forecast_rows)
        logger.info("Total predicted demand: %.2f", total_predicted_demand)

    return result
