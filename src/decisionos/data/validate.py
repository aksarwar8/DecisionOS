import logging

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


class HistoricalSalesError(ValueError):
    """Historical observations cannot be used as a daily sales series."""


def validate_historical_sales(history: pd.DataFrame) -> pd.Series:
    """Validate actual sales and return parsed calendar dates aligned to history."""
    keys = ["product_id", "store_id"]
    required = {*keys, "date", "sales_quantity"}
    missing = required.difference(history.columns)
    if missing:
        raise HistoricalSalesError(f"Missing historical sales columns: {sorted(missing)}.")
    if history.empty:
        raise HistoricalSalesError("Historical data cannot be empty.")
    if history[keys].isna().any().any():
        raise HistoricalSalesError("Historical product and store IDs must be non-null.")

    raw_dates = history["date"]
    try:
        dates = pd.to_datetime(
            raw_dates if pd.api.types.is_datetime64_any_dtype(raw_dates)
            else raw_dates.astype("string"),
            errors="coerce",
            format="mixed",
        )
    except ValueError as error:
        raise HistoricalSalesError("Historical dates must use a consistent timezone.") from error
    if dates.isna().any() or not pd.api.types.is_datetime64_any_dtype(dates):
        raise HistoricalSalesError("Historical dates must be valid and non-null.")
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    dates = dates.dt.normalize()

    quantities = history["sales_quantity"]
    if (not pd.api.types.is_numeric_dtype(quantities)
            or pd.api.types.is_complex_dtype(quantities)
            or pd.api.types.is_bool_dtype(quantities)):
        raise HistoricalSalesError("Historical sales quantities must be real numbers.")
    values = quantities.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values < 0).any():
        raise HistoricalSalesError("Historical sales quantities must be finite and non-negative.")

    observations = history[keys].assign(date=dates)
    if observations.duplicated().any():
        raise HistoricalSalesError("Duplicate product-store-date observations in historical sales.")
    spans = observations.groupby(keys, sort=False, observed=True)["date"].agg(
        ["min", "max", "size"]
    )
    if spans["size"].ne((spans["max"] - spans["min"]).dt.days + 1).any():
        raise HistoricalSalesError("Historical sales contain missing calendar dates.")
    return dates


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str],
    name: str = "DataFrame",
) -> None:
    """
    Validate a DataFrame for basic data quality.

    Checks:
    1. DataFrame is not empty.
    2. Required columns are present.
    3. Required columns contain no missing values.
    4. Duplicate rows are reported.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame.")

    if df.empty:
        raise ValueError(f"{name} is empty.")

    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"{name} is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    missing_values = df[required_columns].isnull().sum()

    columns_with_missing = missing_values[missing_values > 0]

    if not columns_with_missing.empty:
        raise ValueError(
            f"{name} contains missing values:\n"
            f"{columns_with_missing.to_dict()}"
        )

    duplicate_count = df.duplicated().sum()

    if duplicate_count > 0:
        logger.warning("%s contains %s duplicate rows.", name, duplicate_count)

    logger.debug("%s validation passed.", name)
