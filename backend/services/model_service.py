
import logging
from functools import lru_cache

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from src.decisionos.config import get_settings
from src.decisionos.ml.train import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class PredictionInputError(ValueError):
    """The supplied feature vector fails the prediction input contract."""


def configure_mlflow() -> str:
    """Configure MLflow lazily and return the resolved tracking URI."""
    uri = get_settings().resolve_tracking_uri()
    mlflow.set_tracking_uri(uri)
    return uri


@lru_cache(maxsize=1)
def load_forecasting_model_info():
    """
    Load the registered Random Forest model.

    The cached model is reused across API requests.
    Restart the API process to refresh a changed alias.
    """

    configure_mlflow()
    settings = get_settings()
    version = MlflowClient().get_model_version_by_alias(settings.model_name, settings.model_alias)
    model_uri = f"models:/{settings.model_name}/{version.version}"

    model = mlflow.sklearn.load_model(
        model_uri
    )

    logger.info("DecisionOS forecasting model loaded: %s", model_uri)

    return model, str(version.version)


def load_forecasting_model():
    return load_forecasting_model_info()[0]


def predict_demand(model, input_df: pd.DataFrame):
    """
    Generate predictions using the registered model.

    Input must contain the 14 training features.
    """

    if input_df.empty:
        raise PredictionInputError("Input data cannot be empty.")

    missing_columns = (
        set(FEATURE_COLUMNS) - set(input_df.columns)
    )

    if missing_columns:
        raise PredictionInputError(
            f"Missing model features: {sorted(missing_columns)}"
        )

    model_input = input_df[FEATURE_COLUMNS].copy()

    if model_input.isnull().any().any():
        raise PredictionInputError(
            "Model input contains missing feature values."
        )

    predictions = model.predict(model_input)

    return predictions.clip(min=0)
