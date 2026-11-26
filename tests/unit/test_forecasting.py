import numpy as np
import pandas as pd
import pytest

from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.features.lag_features import create_lag_features
from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.hybrid import hybrid_forecast
from src.decisionos.ml.train import FEATURE_COLUMNS


def sales_frame(quantities, product_id=1, store_id=1):
    return pd.DataFrame({
        "product_id": product_id, "store_id": store_id,
        "date": pd.date_range("2021-01-01", periods=len(quantities)),
        "sales_quantity": quantities,
    })


class ModelStub:
    def __init__(self, value=9.5):
        self.value = value
        self.inputs = []

    def predict(self, features):
        self.inputs.append(features.copy())
        return np.full(len(features), self.value)


def test_known_lags_and_rolling_statistics_exclude_current_value():
    first = sales_frame(np.arange(1, 30))
    second = sales_frame(np.arange(101, 130), store_id=2)
    sales = pd.concat([first, second]).sample(frac=1, random_state=17)
    target = first["date"].max()
    features = create_lag_features(sales)
    rows = features.loc[features["date"] == target].set_index("store_id")
    expected = {
        "lag_7": 22, "lag_14": 15, "lag_28": 1,
        "rolling_mean_7": 25, "rolling_mean_28": 14.5, "rolling_std_7": np.sqrt(14 / 3),
    }
    assert rows.loc[1, list(expected)].to_dict() == pytest.approx(expected)
    assert rows.loc[2, "rolling_mean_7"] == 125
    assert rows.loc[2, "lag_28"] == 101
    changed = sales.copy()
    changed.loc[changed["date"] == target, "sales_quantity"] = 9999
    updated = create_lag_features(changed)
    pd.testing.assert_frame_equal(
        features.loc[features["date"] == target, list(expected)],
        updated.loc[updated["date"] == target, list(expected)],
    )


@pytest.mark.parametrize(("value", "feedback"), [(9.5, 9.5), (-3, 0)])
def test_recursive_feedback_uses_clipped_prediction_and_canonical_order(value, feedback):
    history = sales_frame(np.full(28, 2))
    model = ModelStub(value)
    dates = pd.date_range("2021-01-29", periods=7)
    result = recursive_forecast(model, history, dates[::-1])
    assert result["date"].tolist() == dates.tolist()
    assert result["prediction"].tolist() == [feedback] * len(dates)
    assert len(model.inputs) == len(dates)
    assert all(list(frame.columns) == FEATURE_COLUMNS for frame in model.inputs)
    assert model.inputs[0]["rolling_mean_7"].iat[0] == 2
    assert model.inputs[1]["rolling_mean_7"].iat[0] == pytest.approx((12 + feedback) / 7)


def test_insufficient_input_history_is_rejected():
    with pytest.raises(HistoricalSalesError, match="At least 28 observations"):
        recursive_forecast(None, sales_frame(np.zeros(27)), ["2021-01-28"])


def test_demand_segment_boundaries_and_existing_policy():
    levels = [0, 0.5, 1, 1.5, 5, 5.5]
    history = pd.concat([
        sales_frame(np.full(28, level), product_id=product_id)
        for product_id, level in enumerate(levels, start=1)
    ])
    result = hybrid_forecast(ModelStub(), history, ["2021-01-29"]).sort_values("product_id")
    assert result["demand_segment"].tolist() == [
        "Zero average", "Low demand", "Low demand", "Medium demand",
        "Medium demand", "High demand",
    ]
    assert result["selected_model"].tolist() == ["Historical Mean"] + ["Random Forest"] * 5
    assert result["prediction"].tolist() == [0] + [9.5] * 5
