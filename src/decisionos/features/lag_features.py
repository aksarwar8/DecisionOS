
import pandas as pd


def create_lag_features(
    df: pd.DataFrame,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """
    Create historical lag and rolling features for each
    product-store time series.

    Required columns:
        product_id, store_id, date, sales_quantity
    """
    if lags is None:
        lags = [7, 14, 28]

    required_columns = [
        "product_id",
        "store_id",
        "date",
        "sales_quantity",
    ]

    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    result = df.copy()

    result["date"] = pd.to_datetime(result["date"])

    result = result.sort_values(
        ["product_id", "store_id", "date"]
    ).reset_index(drop=True)

    grouped = result.groupby(["product_id", "store_id"])["sales_quantity"]

    # Lag features: historical sales values
    for lag in lags:
        result[f"lag_{lag}"] = grouped.shift(lag)

    # Rolling features: past demand statistics
    shifted_sales = grouped.shift(1)

    result["rolling_mean_7"] = (
        shifted_sales.groupby(
            [result["product_id"], result["store_id"]]
        )
        .rolling(window=7)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )

    result["rolling_mean_28"] = (
        shifted_sales.groupby(
            [result["product_id"], result["store_id"]]
        )
        .rolling(window=28)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )

    result["rolling_std_7"] = (
        shifted_sales.groupby(
            [result["product_id"], result["store_id"]]
        )
        .rolling(window=7)
        .std()
        .reset_index(level=[0, 1], drop=True)
    )

    return result
