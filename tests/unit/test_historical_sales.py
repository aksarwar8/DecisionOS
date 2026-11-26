import numpy as np
import pandas as pd
import pytest

from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales
from src.decisionos.ml.dataset import prepare_ml_dataset
from src.decisionos.ml.forecast import recursive_forecast


@pytest.fixture
def history():
    return pd.DataFrame({
        "product_id": 1, "store_id": 1,
        "date": pd.date_range("2021-01-01", periods=30),
        "sales_quantity": np.zeros(30),
    })


def test_shuffled_series_have_independent_bounds_and_keep_zero_sales(history):
    other = history.iloc[1:].assign(store_id=2)
    combined = pd.concat([history, other], ignore_index=True).sample(frac=1, random_state=4)
    assert len(validate_historical_sales(combined)) == 59
    assert prepare_ml_dataset(combined)["sales_quantity"].tolist() == [0, 0, 0]


@pytest.mark.parametrize(("make_invalid", "message"), [
    (lambda frame: pd.concat([frame, frame.iloc[[1]]]), "Duplicate"),
    (lambda frame: frame.drop(index=1), "missing calendar dates"),
    (lambda frame: frame.assign(sales_quantity=-0.5), "non-negative"),
    (lambda frame: frame.assign(sales_quantity=np.inf), "finite"),
    (lambda frame: frame.assign(sales_quantity=np.nan), "finite"),
    (lambda frame: frame.assign(sales_quantity="invalid"), "real numbers"),
    (lambda frame: frame.assign(date=pd.NaT), "valid and non-null"),
    (lambda frame: frame.assign(date="not a date"), "valid and non-null"),
    (lambda frame: frame.assign(product_id=None), "IDs must be non-null"),
    (lambda frame: frame.drop(columns="store_id"), "Missing historical sales columns"),
])
def test_training_and_recursive_serving_reject_invalid_history(history, make_invalid, message):
    invalid = make_invalid(history)
    with pytest.raises(HistoricalSalesError, match=message):
        prepare_ml_dataset(invalid)
    with pytest.raises(HistoricalSalesError, match=message):
        recursive_forecast(None, invalid, ["2021-02-01"])
