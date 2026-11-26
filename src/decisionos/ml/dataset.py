import logging

import pandas as pd

from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.features.pipeline import build_features


logger = logging.getLogger(__name__)


def prepare_ml_dataset(
    sales_df: pd.DataFrame,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """
    Prepare a feature-engineered dataset for ML forecasting.

    Workflow:
        1. Generate time, lag, and rolling features.
        2. Remove rows with missing feature values.
        3. Return a clean dataset for model training.
    """

    featured_df = build_features(
        sales_df.assign(date=validate_historical_sales(sales_df)),
        lags=lags,
    )

    # Identify feature columns that contain missing values.
    feature_columns = [
        column
        for column in featured_df.columns
        if column.startswith("lag_")
        or column.startswith("rolling_")
    ]

    # Remove rows where historical features are unavailable.
    clean_df = featured_df.dropna(
        subset=feature_columns
    ).copy()

    clean_df = clean_df.reset_index(drop=True)

    logger.info("Original dataset shape: %s", featured_df.shape)
    logger.info("Clean ML dataset shape: %s", clean_df.shape)
    logger.info("Rows removed: %s", len(featured_df) - len(clean_df))

    return clean_df
