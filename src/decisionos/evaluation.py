
import numpy as np


def evaluate_forecast(actual, predicted):
    """Calculate forecasting error metrics."""

    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))

    print("\n--- Forecast Evaluation ---")
    print(f"MAE: {mae:,.2f}")
    print(f"RMSE: {rmse:,.2f}")

    return mae, rmse
