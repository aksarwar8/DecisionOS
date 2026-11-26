import numpy as np
import pandas as pd
import pytest

from src.decisionos.ml.evaluate import evaluate_forecasts


def test_metrics_for_perfect_predictions():
    actual = pd.Series([0, 2, 4])
    assert evaluate_forecasts(actual, actual) == {
        "MAE": 0, "RMSE": 0, "WAPE": 0, "evaluated_rows": 3,
    }


def test_metrics_for_known_errors():
    # Absolute errors are 1 and 3. Actual demand totals 10.
    assert evaluate_forecasts([4, 6], [3, 9]) == pytest.approx({
        "MAE": 2, "RMSE": np.sqrt(5), "WAPE": 40, "evaluated_rows": 2,
    })


def test_wape_is_undefined_for_all_zero_demand():
    metrics = evaluate_forecasts([0, 0], [1, 1])
    assert metrics["MAE"] == metrics["RMSE"] == 1
    assert np.isnan(metrics["WAPE"])


def test_non_finite_pairs_are_excluded():
    metrics = evaluate_forecasts([4, np.nan, 4], [3, 10, np.inf])
    assert metrics == {"MAE": 1, "RMSE": 1, "WAPE": 25, "evaluated_rows": 1}
    with pytest.raises(ValueError, match="No valid predictions"):
        evaluate_forecasts([np.nan], [1])


@pytest.mark.parametrize(("actual", "predicted"), [
    ([1, 2], [1]),
    ([[1], [2]], [1, 2]),
    (1, 1),
])
def test_incompatible_shapes_are_rejected(actual, predicted):
    with pytest.raises(ValueError, match="one-dimensional and equal in length"):
        evaluate_forecasts(actual, predicted)
