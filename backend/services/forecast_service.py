
import pandas as pd

from backend.services.model_service import (
    load_forecasting_model,
)

from src.decisionos.data.extract_forecast import (
    extract_product_store_history,
)
from src.decisionos.data.validate import HistoricalSalesError

from src.decisionos.ml.hybrid import hybrid_forecast


ALLOWED_HORIZONS = [7, 14, 28]


def generate_product_forecast(
    product_id: int,
    store_id: int,
    horizon: int,
) -> pd.DataFrame:
    """
    Generate a multi-day hybrid demand forecast
    for one product-store pair.
    """

    if horizon not in ALLOWED_HORIZONS:
        raise HistoricalSalesError(
            f"Invalid horizon. Choose one of: {ALLOWED_HORIZONS}."
        )

    # Retrieve the latest 90 calendar days of actual sales.
    history_df = extract_product_store_history(
        product_id=product_id,
        store_id=store_id,
        lookback_days=90,
    )

    # Forecast starts the day after the latest actual observation.
    latest_date = history_df["date"].max()

    future_dates = pd.date_range(
        start=latest_date + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    ).tolist()

    # Load the registered Random Forest model.
    model = load_forecasting_model()

    # Apply the existing hybrid forecasting policy.
    forecast_df = hybrid_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )

    return forecast_df
