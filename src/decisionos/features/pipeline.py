
import pandas as pd

from src.decisionos.features.time_features import create_time_features
from src.decisionos.features.lag_features import create_lag_features


def build_features(
    df: pd.DataFrame,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """
    Build time-based, lag, and rolling features.

    Expected columns:
        product_id, store_id, date, sales_quantity
    """

    required_columns = [
        "product_id",
        "store_id",
        "date",
        "sales_quantity",
    ]

    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Input data is missing columns: {sorted(missing_columns)}"
        )

    # Step 1: Calendar features
    featured_df = create_time_features(df)

    # Step 2: Historical lag and rolling features
    featured_df = create_lag_features(
        featured_df,
        lags=lags,
    )

    return featured_df
