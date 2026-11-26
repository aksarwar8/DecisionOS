import numpy as np
import pandas as pd
import pytest

from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.ml.batch_forecast import forecast_aligned_batch
from src.decisionos.ml.hybrid import hybrid_forecast


class DeterministicModel:
    def __init__(self):
        self.calls = []

    def predict(self, features):
        self.calls.append(features.copy())
        return features["rolling_mean_7"].to_numpy() + features["lag_7"].to_numpy() / 10


def test_batch_matches_independent_forecasts():
    dates = pd.date_range("2021-01-01", periods=35)
    history = pd.concat([
        pd.DataFrame({"product_id": product, "store_id": store, "date": dates,
                      "sales_quantity": (np.arange(35) + product) % 7})
        for product, store in [(1, 1), (1, 2), (2, 1)]
    ], ignore_index=True).sample(frac=1, random_state=4)
    model = DeterministicModel()
    batch = forecast_aligned_batch(model, history, 14)
    assert len(model.calls) == 14
    assert all(len(features) == 3 for features in model.calls)
    future = pd.date_range("2021-02-05", periods=14).tolist()
    individual = pd.concat([
        hybrid_forecast(model, group, future)
        for _, group in history.groupby(["product_id", "store_id"])
    ])
    keys = ["product_id", "store_id", "date"]
    merged = batch.merge(individual, on=keys, suffixes=("_batch", "_single"), validate="one_to_one")
    assert len(merged) == 42
    np.testing.assert_allclose(merged["prediction_batch"], merged["prediction_single"],
                               rtol=1e-12, atol=1e-12)
    assert (merged["selected_model_batch"] == merged["selected_model_single"]).all()


def test_batch_rejects_different_origins():
    dates = pd.date_range("2021-01-01", periods=30)
    first = pd.DataFrame({"product_id": 1, "store_id": 1, "date": dates, "sales_quantity": 1})
    second = first.iloc[:-1].assign(store_id=2)
    with pytest.raises(HistoricalSalesError, match="same date"):
        forecast_aligned_batch(DeterministicModel(), pd.concat([first, second]), 7)
