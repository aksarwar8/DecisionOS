import logging

from pathlib import Path
import tempfile

import mlflow
import pandas as pd

from mlflow.tracking import MlflowClient

from src.decisionos.config import FORECAST_ARTIFACT_NAME, get_settings
from src.decisionos.data.pipeline import build_sales_dataset
from src.decisionos.ml.evaluate import evaluate_forecasts




logger = logging.getLogger(__name__)


def evaluate_forecasting_run(training_run_id: str) -> dict:
    """
    Evaluate a previously logged forecasting run.

    Workflow:
        1. Retrieve training run metadata.
        2. Download its forecast CSV from MLflow.
        3. Extract actual sales from PostgreSQL.
        4. Match actual and predicted demand.
        5. Calculate MAE, RMSE and WAPE.
        6. Log evaluation results in a separate MLflow run.
    """

    # --------------------------------------------------
    # 1. Configure MLflow
    # --------------------------------------------------

    settings = get_settings()
    tracking_uri = settings.resolve_tracking_uri()
    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_experiment(settings.mlflow_experiment_name)

    client = MlflowClient(
        tracking_uri=tracking_uri
    )

    logger.info("DECISIONOS FORECAST EVALUATION")

    # --------------------------------------------------
    # 2. Retrieve original training run
    # --------------------------------------------------

    logger.info("\n[1/5] Retrieving training run...")

    training_run = client.get_run(training_run_id)

    if training_run.info.status != "FINISHED":
        raise ValueError(
            "The training run must have FINISHED status."
        )

    params = training_run.data.params

    required_params = [
        "forecast_start_date",
        "forecast_end_date",
    ]

    missing_params = [
        key for key in required_params
        if key not in params
    ]

    if missing_params:
        raise ValueError(
            f"Missing training run parameters: {missing_params}"
        )

    forecast_start = pd.Timestamp(
        params["forecast_start_date"]
    )

    forecast_end = pd.Timestamp(
        params["forecast_end_date"]
    )

    logger.info("Training run ID: %s", training_run_id)
    logger.info("Forecast start: %s", forecast_start.date())
    logger.info("Forecast end: %s", forecast_end.date())

    # --------------------------------------------------
    # 3. Download forecast artifact
    # --------------------------------------------------

    logger.info("\n[2/5] Downloading forecast artifact...")

    with tempfile.TemporaryDirectory() as temp_dir:

        forecast_path = client.download_artifacts(
            run_id=training_run_id,
            path=FORECAST_ARTIFACT_NAME,
            dst_path=temp_dir,
        )

        forecasts = pd.read_csv(
            forecast_path,
            parse_dates=["date"],
        )

        required_forecast_columns = [
            "product_id",
            "store_id",
            "date",
            "prediction",
        ]

        missing_columns = (
            set(required_forecast_columns)
            - set(forecasts.columns)
        )

        if missing_columns:
            raise ValueError(
                f"Forecast artifact is missing columns: "
                f"{sorted(missing_columns)}"
            )

        forecasts = forecasts[
            required_forecast_columns
        ].copy()

        if forecasts.empty:
            raise ValueError("Forecast artifact is empty.")

        if forecasts.duplicated(
            ["product_id", "store_id", "date"]
        ).any():
            raise ValueError(
                "Duplicate product-store-date predictions found."
            )

        if forecasts["prediction"].isna().any():
            raise ValueError(
                "Forecast artifact contains missing predictions."
            )

        logger.info("Forecast rows: %s", len(forecasts))

        # --------------------------------------------------
        # 4. Extract actual sales
        # --------------------------------------------------

        logger.info("\n[3/5] Extracting actual sales from PostgreSQL...")

        actual = build_sales_dataset(
            start_date=str(forecast_start.date()),
            end_date=str(forecast_end.date()),
        )

        actual = actual[
            ["product_id", "store_id", "date", "sales_quantity"]
        ].copy()

        logger.info("Actual sales rows: %s", len(actual))

        # --------------------------------------------------
        # 5. Match predictions with actual sales
        # --------------------------------------------------

        logger.info("\n[4/5] Matching actual and predicted demand...")

        comparison = actual.merge(
            forecasts,
            on=["product_id", "store_id", "date"],
            how="outer",
            validate="one_to_one",
            indicator=True,
        )

        unmatched = comparison[
            comparison["_merge"] != "both"
        ]

        if not unmatched.empty:
            raise ValueError(
                f"Found {len(unmatched)} unmatched actual/"
                "forecast records. Evaluation stopped."
            )

        comparison = comparison.drop(
            columns=["_merge"]
        )

        metrics = evaluate_forecasts(
            actual=comparison["sales_quantity"],
            predicted=comparison["prediction"],
        )

        logger.info("Matched evaluation rows: %s", len(comparison))

        # --------------------------------------------------
        # 6. Log evaluation in a separate MLflow run
        # --------------------------------------------------

        logger.info("\n[5/5] Logging evaluation results...")

        with mlflow.start_run(
            run_name=f"evaluation_{forecast_start.date()}",
            tags={
                "run_type": "evaluation",
                "training_run_id": training_run_id,
            },
        ) as evaluation_run:

            mlflow.log_params({
                "training_run_id": training_run_id,
                "evaluation_start_date": str(forecast_start.date()),
                "evaluation_end_date": str(forecast_end.date()),
                "evaluation_horizon_days": (
                    forecast_end - forecast_start
                ).days + 1,
                "evaluation_rows": len(comparison),
            })

            mlflow.log_metrics({
                "MAE": metrics["MAE"],
                "RMSE": metrics["RMSE"],
                "WAPE": metrics["WAPE"],
                "evaluated_rows": metrics["evaluated_rows"],
                "total_actual_demand": float(
                    comparison["sales_quantity"].sum()
                ),
                "total_predicted_demand": float(
                    comparison["prediction"].sum()
                ),
            })

            # Save complete comparison as an MLflow artifact.
            comparison_path = (
                Path(temp_dir) / "evaluation_results.csv"
            )

            comparison.to_csv(
                comparison_path,
                index=False,
            )

            mlflow.log_artifact(
                str(comparison_path)
            )

            result = {
                "evaluation_run_id": evaluation_run.info.run_id,
                "training_run_id": training_run_id,
                **metrics,
                "total_actual_demand": float(
                    comparison["sales_quantity"].sum()
                ),
                "total_predicted_demand": float(
                    comparison["prediction"].sum()
                ),
            }

    # --------------------------------------------------
    # 7. Display evaluation results
    # --------------------------------------------------

    logger.info("FORECAST EVALUATION COMPLETED")

    logger.info("Training run: %s", result["training_run_id"])
    logger.info("Evaluation run: %s", result["evaluation_run_id"])

    for metric in ["MAE", "RMSE", "WAPE"]:
        logger.info("%s: %.4f", metric, result[metric])

    logger.info("Evaluated rows: %s", result["evaluated_rows"])
    logger.info("Actual demand: %.2f", result["total_actual_demand"])
    logger.info("Predicted demand: %.2f", result["total_predicted_demand"])

    return result
