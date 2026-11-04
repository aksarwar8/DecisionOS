
import numpy as np


def evaluate_forecast(actual, predicted):
    """
    Evaluate forecasting performance using
    MAE, RMSE, and WAPE.
    """

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    # Mean Absolute Error
    mae = np.mean(np.abs(actual - predicted))

    # Root Mean Squared Error
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))

    # Weighted Absolute Percentage Error
    total_actual = np.sum(np.abs(actual))

    if total_actual != 0:
        wape = (
            np.sum(np.abs(actual - predicted))
            / total_actual
        ) * 100
    else:
        wape = np.nan

    print("\n========== Forecast Evaluation ==========")
    print(f"MAE:  {mae:,.2f}")
    print(f"RMSE: {rmse:,.2f}")
    print(f"WAPE: {wape:.2f}%")

    return mae, rmse, wape
