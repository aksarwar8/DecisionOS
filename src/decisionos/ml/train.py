import logging

import pandas as pd

from sklearn.ensemble import RandomForestRegressor


logger = logging.getLogger(__name__)


FEATURE_COLUMNS = [
    "product_id",
    "store_id",
    "year",
    "month",
    "day",
    "day_of_week",
    "week_of_year",
    "is_weekend",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "rolling_std_7",
]

TARGET_COLUMN = "sales_quantity"


def train_random_forest(
    train_df: pd.DataFrame,
    n_estimators: int = 100,
    random_state: int = 42,
):
    """
    Train a Random Forest regression model for demand forecasting.
    """

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=15,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    logger.info("Random Forest training completed.")
    logger.info("Training rows: %s", len(X_train))
    logger.info("Number of features: %s", len(FEATURE_COLUMNS))

    return model
