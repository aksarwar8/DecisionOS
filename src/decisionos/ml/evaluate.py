
import numpy as np


def evaluate_forecasts(
    actual,
    predicted,
) -> dict:
    """
    Evaluate forecasting performance using MAE, RMSE, and WAPE.

    Accepts both Pandas Series and NumPy arrays.
    """

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.ndim != 1 or predicted.ndim != 1 or actual.shape != predicted.shape:
        raise ValueError("Actual and predicted values must be one-dimensional and equal in length.")

    valid_mask = (
        np.isfinite(actual)
        & np.isfinite(predicted)
    )

    actual = actual[valid_mask]
    predicted = predicted[valid_mask]

    if len(actual) == 0:
        raise ValueError(
            "No valid predictions available for evaluation."
        )

    errors = actual - predicted

    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors ** 2))

    total_actual = np.sum(np.abs(actual))

    if total_actual == 0:
        wape = np.nan
    else:
        wape = (
            np.sum(np.abs(errors))
            / total_actual
            * 100
        )

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "WAPE": float(wape),
        "evaluated_rows": int(len(actual)),
    }
