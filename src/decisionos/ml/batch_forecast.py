"""Common-origin batch forecasting using the existing hybrid policy."""

import pandas as pd

from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales
from src.decisionos.ml.hybrid import hybrid_forecast


def forecast_aligned_batch(model, history_df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Forecast multiple complete daily histories with one shared forecast origin."""
    if horizon not in (7, 14, 28):
        raise ValueError("Forecast horizon must be 7, 14, or 28 days.")
    history = history_df.assign(date=validate_historical_sales(history_df))
    groups = history.groupby(["product_id", "store_id"], sort=False)["date"]
    if groups.size().lt(28).any():
        raise HistoricalSalesError("Every product-store pair needs at least 28 observations.")
    latest = groups.max()
    if latest.nunique() != 1:
        raise HistoricalSalesError("All product-store histories must end on the same date.")
    dates = pd.date_range(latest.iloc[0] + pd.Timedelta(days=1), periods=horizon, freq="D")
    return hybrid_forecast(model, history, dates.tolist())
