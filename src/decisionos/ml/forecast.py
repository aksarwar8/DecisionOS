
import numpy as np
import pandas as pd

from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales
from src.decisionos.ml.train import FEATURE_COLUMNS


def recursive_forecast(
    model,
    history_df: pd.DataFrame,
    future_dates: list,
) -> pd.DataFrame:
    """
    Generate multi-step recursive demand forecasts.

    Historical actual sales are used to initialize the forecast.
    Subsequent predictions are fed back as historical observations.

    Required history columns:
        product_id, store_id, date, sales_quantity
    """

    history = history_df.assign(date=validate_historical_sales(history_df))

    history = history.sort_values(
        ["product_id", "store_id", "date"]
    )

    # Store historical sales separately for every product-store pair.
    series = {}

    for (product_id, store_id), group in history.groupby(
        ["product_id", "store_id"]
    ):
        values = group["sales_quantity"].astype(float).tolist()

        if len(values) < 28:
            raise HistoricalSalesError(
                f"Insufficient history for product {product_id}, "
                f"store {store_id}. At least 28 observations required."
            )

        series[(product_id, store_id)] = values

    future_dates = sorted(
        pd.to_datetime(future_dates)
    )

    if not future_dates:
        raise ValueError("Provide at least one future date.")

    if len(set(future_dates)) != len(future_dates):
        raise ValueError("Future dates must be unique.")

    if future_dates[0] <= history["date"].max():
        raise ValueError(
            "All future dates must be after the historical data."
        )

    forecast_rows = []

    # Predict one date at a time.
    for forecast_date in future_dates:

        feature_rows = []
        group_keys = list(series.keys())

        for product_id, store_id in group_keys:

            values = series[(product_id, store_id)]

            row = {
                "product_id": product_id,
                "store_id": store_id,
                "year": forecast_date.year,
                "month": forecast_date.month,
                "day": forecast_date.day,
                "day_of_week": forecast_date.dayofweek,
                "week_of_year": forecast_date.isocalendar().week,
                "is_weekend": int(forecast_date.dayofweek >= 5),
                "lag_7": values[-7],
                "lag_14": values[-14],
                "lag_28": values[-28],
                "rolling_mean_7": np.mean(values[-7:]),
                "rolling_mean_28": np.mean(values[-28:]),
                "rolling_std_7": np.std(values[-7:], ddof=1),
            }

            feature_rows.append(row)

        X_future = pd.DataFrame(feature_rows)[FEATURE_COLUMNS]

        predictions = model.predict(X_future)

        predictions = np.maximum(predictions, 0)

        # Feed today's predictions into the history for tomorrow.
        for (product_id, store_id), prediction in zip(
            group_keys, predictions
        ):
            series[(product_id, store_id)].append(
                float(prediction)
            )

            forecast_rows.append({
                "product_id": product_id,
                "store_id": store_id,
                "date": forecast_date,
                "prediction": float(prediction),
            })

    return pd.DataFrame(forecast_rows)
