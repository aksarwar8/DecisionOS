
import pandas as pd


def seasonal_naive_forecast(
    df: pd.DataFrame,
    seasonal_period: int = 7,
) -> pd.DataFrame:
    """
    Seasonal naive forecasting.

    Predicts demand using sales from the same seasonal
    period in the past.

    Required columns:
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
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if seasonal_period < 1:
        raise ValueError("seasonal_period must be >= 1.")

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])

    result = result.sort_values(
        ["product_id", "store_id", "date"]
    ).reset_index(drop=True)

    result["prediction"] = (
        result.groupby(["product_id", "store_id"])["sales_quantity"]
        .shift(seasonal_period)
    )

    return result



def mean_baseline_forecast(
    train_df: pd.DataFrame,
    target_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Predict sales using the average historical sales
    for each product-store combination.

    The mean is calculated using training data only.
    """

    required_columns = [
        "product_id",
        "store_id",
        "sales_quantity",
    ]

    for df_name, df in [
        ("train_df", train_df),
        ("target_df", target_df),
    ]:
        missing_columns = set(required_columns) - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"{df_name} is missing columns: {sorted(missing_columns)}"
            )

    historical_means = (
        train_df.groupby(["product_id", "store_id"])["sales_quantity"]
        .mean()
        .reset_index(name="prediction")
    )

    result = target_df.merge(
        historical_means,
        on=["product_id", "store_id"],
        how="left",
    )

    return result
