
import pandas as pd


def transform_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize and transform extracted sales data.

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
            f"Sales data is missing columns: {sorted(missing_columns)}"
        )

    transformed = df.copy()

    # Standardize data types
    transformed["product_id"] = transformed["product_id"].astype("int32")
    transformed["store_id"] = transformed["store_id"].astype("int32")
    transformed["date"] = pd.to_datetime(transformed["date"])
    quantities = transformed["sales_quantity"]
    if pd.api.types.is_integer_dtype(quantities) and not quantities.empty:
        limits = quantities.min(), quantities.max()
        if quantities.notna().all() and -(2**31) <= limits[0] <= limits[1] < 2**31:
            transformed["sales_quantity"] = quantities.astype("int32")

    # Add calendar-based features
    transformed["year"] = transformed["date"].dt.year.astype("int16")
    transformed["month"] = transformed["date"].dt.month.astype("int8")
    transformed["day"] = transformed["date"].dt.day.astype("int8")
    transformed["day_of_week"] = (
        transformed["date"].dt.dayofweek.astype("int8")
    )
    transformed["week_of_year"] = (
        transformed["date"].dt.isocalendar().week.astype("int8")
    )

    # Keep records chronologically ordered
    transformed = transformed.sort_values(
        ["date", "store_id", "product_id"]
    ).reset_index(drop=True)

    return transformed


def aggregate_daily_sales(
    df: pd.DataFrame,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    """
    Aggregate sales quantities by selected dimensions.

    Default aggregation: date, store_id, product_id.
    """
    if "sales_quantity" not in df.columns:
        raise ValueError("Sales data must contain sales_quantity.")

    if group_by is None:
        group_by = ["date", "store_id", "product_id"]

    missing_columns = set(group_by) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Aggregation columns are missing: {sorted(missing_columns)}"
        )

    aggregated = (
        df.groupby(group_by, as_index=False)["sales_quantity"]
        .sum()
    )

    return aggregated
