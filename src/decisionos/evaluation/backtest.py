"""Chronological split and exact prediction alignment for research."""

import pandas as pd


def rolling_windows(origins, training_days, horizon):
    if training_days < 28 or horizon not in (7, 14, 28):
        raise ValueError("Use at least 28 training days and a 7, 14, or 28-day horizon.")
    for value in origins:
        origin = pd.Timestamp(value).normalize()
        yield (origin - pd.Timedelta(days=training_days - 1), origin,
               origin + pd.Timedelta(days=1), origin + pd.Timedelta(days=horizon))


def align_predictions(actual, predicted):
    keys = ["product_id", "store_id", "date"]
    result = actual.merge(predicted, on=keys, how="outer", validate="one_to_one", indicator=True)
    if not result["_merge"].eq("both").all():
        raise ValueError("Prediction and actual keys must match exactly.")
    return result.drop(columns="_merge")
