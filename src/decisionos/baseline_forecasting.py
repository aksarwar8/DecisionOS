
import numpy as np


def seasonal_naive_forecast(test_data):
    """
    Seasonal naive forecast using sales from
    the same weekday in the previous week.
    """

    actual = test_data["target"].to_numpy()
    predictions = test_data["lag_7"].to_numpy()

    return actual, predictions


def evaluate_baseline(actual, predicted):
    """
    Evaluate baseline using MAE, RMSE, and WAPE.
    """

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    mae = np.mean(np.abs(actual - predicted))

    rmse = np.sqrt(
        np.mean((actual - predicted) ** 2)
    )

    total_actual = np.sum(np.abs(actual))

    if total_actual != 0:
        wape = (
            np.sum(np.abs(actual - predicted))
            / total_actual
        ) * 100
    else:
        wape = np.nan

    print("\n========== Seasonal Naive Evaluation ==========")
    print(f"MAE:  {mae:,.2f}")
    print(f"RMSE: {rmse:,.2f}")
    print(f"WAPE: {wape:.2f}%")

    return mae, rmse, wape
