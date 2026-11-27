import numpy as np
import pandas as pd
import pytest

from src.decisionos.evaluation.optimization import HurdleModel, direct_training
from src.decisionos.ml.train import FEATURE_COLUMNS


def test_hurdle_all_zero_and_positive():
    x = pd.DataFrame({"a": np.arange(40)})
    assert np.all(HurdleModel(estimators=5).fit(x, np.zeros(40)).predict(x) == 0)
    assert np.all(HurdleModel(estimators=5).fit(x, np.ones(40)).predict(x) >= 0)


def test_direct_training_never_reaches_beyond_training():
    dates = pd.date_range("2020-01-01", periods=35)
    data = pd.DataFrame({name: np.ones(35) for name in FEATURE_COLUMNS})
    data["product_id"], data["store_id"] = 1, 1
    data["date"], data["sales_quantity"] = dates, np.arange(35)
    result = direct_training(data, stride=7, horizon=28)
    assert len(result) == 56
    assert result.lead.max() == 28
    assert result.target.max() == 34
    assert result.query("lead==28").target.tolist() == [27, 34]
    shorter = direct_training(data.iloc[:27], horizon=28)
    assert shorter.empty


def test_hurdle_requires_dataframe_features():
    model = HurdleModel(estimators=5)
    with pytest.raises((ValueError, IndexError)):
        model.fit(pd.DataFrame({"a": []}), [])
