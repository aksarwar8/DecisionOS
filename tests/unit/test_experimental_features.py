import numpy as np
import pandas as pd
import pytest

from src.decisionos.evaluation.experimental_features import (
    FAMILIES, columns, feature_row, fit_encodings, historical_prices,
)
from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.train import FEATURE_COLUMNS


def context():
    data = {"category": "FOODS", "department": "FOODS_1", "state": "CA",
            "event_name_1": "A", "event_name_2": "B", "event_type_1": "X", "event_type_2": "Y"}
    encodings = fit_encodings(pd.DataFrame([data]))
    calendar = {**data, "snap_ca": 1, "snap_tx": 0, "snap_wi": 0}
    quotes = pd.DataFrame({"week_end": pd.to_datetime(["2020-01-01", "2020-01-08"]),
                           "sell_price": [2.0, 4.0]})
    return data, encodings, calendar, quotes


def test_price_cutoff_and_missing_quotes():
    _, _, _, quotes = context()
    assert historical_prices(quotes, "2020-01-08")["price_last"] == 2
    assert historical_prices(quotes, "2019-01-01")["price_available"] == 0
    assert historical_prices(quotes, "2020-01-09")["price_change"] == 1


def test_events_snap_and_zero_history():
    data, encodings, calendar, quotes = context()
    row = feature_row([0] * 90, "2020-01-09", 1, 2, calendar, data, encodings, quotes, "2020-01-09")
    assert row["event_1"] == row["event_2"] == row["snap_state"] == 1
    assert row["event_name_2_code"] == 0
    assert np.isnan(row["adi_90"]) and np.isnan(row["ratio_7_28"])
    data["state"] = "TX"
    assert feature_row([0]*90, "2020-01-09", 1, 2, calendar, data, encodings, quotes, "2020-01-09")["snap_state"] == 0


def test_feature_contract_and_recursive_parity():
    class Capture:
        data = None

        def predict(self, frame):
            self.data = frame.copy()
            return np.array([3.0])
    dates = pd.date_range("2019-10-01", periods=90)
    values = np.arange(90) % 6
    history = pd.DataFrame({"product_id": 1, "store_id": 2, "date": dates, "sales_quantity": values})
    date = dates[-1] + pd.Timedelta(days=1)
    model = Capture()
    recursive_forecast(model, history, [date])
    data, encodings, calendar, quotes = context()
    row = feature_row(values, date, 1, 2, calendar, data, encodings, quotes, date)
    np.testing.assert_allclose(model.data.iloc[0].to_numpy(dtype=float),
                               [row[name] for name in FEATURE_COLUMNS])
    updated = feature_row([*values, 3], date + pd.Timedelta(days=1), 1, 2,
                          calendar, data, encodings, quotes, date)
    assert updated["lag_1"] == 3 and updated["lag_7"] == values[-6]
    assert len(columns(["canonical"])) == 14
    assert len(columns(list(FAMILIES))) == sum(map(len, FAMILIES.values()))
    with pytest.raises(ValueError):
        columns(["pricing"])


def test_unknown_metadata_code_is_stable():
    data, encodings, calendar, quotes = context()
    data["category"] = "UNSEEN"
    row = feature_row([1]*90, "2020-01-09", 1, 2, calendar, data, encodings, quotes, "2020-01-09")
    assert row["category_code"] == -1
