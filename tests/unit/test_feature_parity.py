import numpy as np
import pandas as pd
import pytest

from src.decisionos.data.transform import transform_sales
from src.decisionos.ml.dataset import prepare_ml_dataset
from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.train import FEATURE_COLUMNS


class CapturingModel:
    def __init__(self):
        self.inputs = []

    def predict(self, features):
        # Record the exact model input while keeping forecasting independent of a trained model.
        self.inputs.append(features.copy())
        return np.full(len(features), 2.5)


@pytest.fixture(scope="module")
def sales_and_training_features():
    dates = pd.date_range("2020-11-25", periods=60, freq="D")
    # Shared IDs and distinct sales sequences exercise grouping by both keys.
    pairs = [(1, 10), (1, 11), (2, 10)]
    rows = [
        (product, store, date, (i * i + 3 * i * product + 7 * store) % 29 + product + store)
        for product, store in pairs
        for i, date in enumerate(dates)
    ]
    sales = pd.DataFrame(
        rows, columns=["product_id", "store_id", "date", "sales_quantity"]
    ).sample(frac=1, random_state=2)
    return sales, prepare_ml_dataset(transform_sales(sales))


@pytest.mark.parametrize(
    "target_date",
    ["2020-12-31", "2021-01-01", "2021-01-03", "2021-01-04", "2021-01-17"],
)
def test_recursive_forecast_matches_training_features(
    target_date, sales_and_training_features
):
    sales, training = sales_and_training_features
    target = pd.Timestamp(target_date)
    model = CapturingModel()

    recursive_forecast(model, sales.loc[sales["date"] < target], [target])

    assert len(model.inputs) == 1, f"{target_date}: expected one prediction call"
    actual = model.inputs[0]
    assert list(actual.columns) == FEATURE_COLUMNS, (
        f"{target_date}: recursive input must match the canonical feature names and order"
    )
    expected = training.loc[training["date"] == target, FEATURE_COLUMNS]

    keys = ["product_id", "store_id"]
    expected = expected.set_index(keys, drop=False, verify_integrity=True).sort_index()
    actual = actual.set_index(keys, drop=False, verify_integrity=True).sort_index()
    assert len(expected) == 3, f"{target_date}: expected three training product-store pairs"
    assert actual.index.tolist() == expected.index.tolist(), (
        f"{target_date}: recursive and training product-store pairs differ"
    )

    for feature in FEATURE_COLUMNS:
        np.testing.assert_allclose(
            actual[feature].to_numpy(),
            expected[feature].to_numpy(),
            rtol=1e-12,
            atol=1e-12,
            equal_nan=False,
            err_msg=(
                f"{target_date}: mismatch for {feature} at product-store pairs "
                f"{expected.index.tolist()}"
            ),
        )
