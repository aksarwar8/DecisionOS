from src.decisionos.evaluation.backtest import align_predictions, rolling_windows
from src.decisionos.evaluation.metrics import score
from src.decisionos.ml.baselines import baseline_forecast

import numpy as np
import pandas as pd
import pytest


def test_baselines_and_recursive_seasonal():
    assert baseline_forecast([1, 2, 3], 3, "mean").tolist() == [2, 2, 2]
    assert baseline_forecast([1, 2, 3], 2, "naive").tolist() == [3, 3]
    assert baseline_forecast(range(7), 9, "seasonal_7").tolist() == [0, 1, 2, 3, 4, 5, 6, 0, 1]
    with pytest.raises(ValueError):
        baseline_forecast([1], 7, "seasonal_7")


def test_intermittent_and_zero():
    for method in ("croston", "sba", "tsb"):
        assert baseline_forecast([0] * 30, 7, method).tolist() == [0] * 7
    assert baseline_forecast([0, 1, 0, 1], 1, "croston", alpha=0.5)[0] == pytest.approx(0.5)
    assert baseline_forecast([0, 1, 0, 1], 1, "sba", alpha=0.5)[0] == pytest.approx(0.375)
    assert baseline_forecast([1, 0, 0], 1, "tsb", beta=0.5)[0] == pytest.approx(0.25)


def test_metrics_training_scale_and_zero():
    result = score([0, 0], [1, 1], [2, 2, 2])
    assert result["wape"] is None and result["rmsse"] is None and result["bias"] == 1
    assert score([3, 5], [4, 4], [1, 2, 3])["rmsse"] == 1
    with pytest.raises(ValueError):
        score([1], [np.nan], [1, 2])


def test_windows_and_alignment():
    start, origin, first, last = next(rolling_windows(["2020-01-31"], 30, 7))
    assert (str(start.date()), str(origin.date()), str(first.date()), str(last.date())) == (
        "2020-01-02", "2020-01-31", "2020-02-01", "2020-02-07")
    actual = pd.DataFrame({"product_id": [1], "store_id": [2], "date": ["2020-02-01"], "sales_quantity": [0]})
    predicted = actual[["product_id", "store_id", "date"]].assign(prediction=0)
    assert len(align_predictions(actual, predicted)) == 1
    with pytest.raises(ValueError):
        align_predictions(actual, predicted.iloc[:0])
