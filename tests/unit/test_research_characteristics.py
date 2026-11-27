import numpy as np
import pandas as pd
import pytest

from src.decisionos.evaluation.characterize import aggregate_level, characterize, stratified_select, summarize


def test_characteristics_and_zero_history():
    assert characterize([0, 0, 0])["classification"] == "All zero"
    assert characterize([1, 1, 1])["classification"] == "Smooth"
    assert characterize([0, 1, 0, 1])["classification"] == "Intermittent"
    assert characterize([0, 1, 0, 8])["classification"] == "Lumpy"
    assert characterize([0, 1])["positive_cv2"] is None
    with pytest.raises(ValueError):
        characterize([1, np.nan])


def test_selection_is_deterministic_and_stratified():
    frame = pd.DataFrame({"product_id": range(8), "store_id": [1]*8,
                          "category": ["A"]*4 + ["B"]*4, "state": ["CA"]*8,
                          "segment": ["Low demand"]*8, "classification": ["Smooth"]*8})
    first = stratified_select(frame, 4, 42)
    assert first.equals(stratified_select(frame, 4, 42))
    assert set(first.category) == {"A", "B"}


def test_aggregation_scores_after_summing():
    frame = pd.DataFrame({"method": ["x", "x"], "origin": ["a", "a"],
                          "date": ["d", "d"], "store_id": [1, 1],
                          "sales_quantity": [1, 1], "prediction": [0, 2]})
    result = summarize(aggregate_level(frame, ["store_id"]), ["method"])
    assert result.iloc[0].wape == 0
    assert summarize(frame, ["method"]).iloc[0].wape == 100

def test_selection_ignores_future_observations():
    frame = pd.DataFrame({"product_id": [1, 2], "store_id": [1, 1],
                          "category": ["A", "A"], "state": ["CA", "CA"],
                          "segment": ["Low demand", "Low demand"],
                          "classification": ["Intermittent", "Intermittent"],
                          "future_demand": [0, 100]})
    selected = stratified_select(frame, 1, 3).product_id.tolist()
    frame["future_demand"] = [100000, 0]
    assert stratified_select(frame, 1, 3).product_id.tolist() == selected
