"""Demand diagnostics computed strictly from a single training window."""

import numpy as np
import pandas as pd


def characterize(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Demand must be a nonempty finite nonnegative vector.")
    average = values.mean()
    positive = values[values > 0]
    std = values.std(ddof=0)
    segment = ("Zero average" if average == 0 else "Low demand" if average <= 1
               else "Medium demand" if average <= 5 else "High demand")
    adi = len(values) / len(positive) if len(positive) else None
    cv2 = float((positive.std(ddof=0) / positive.mean()) ** 2) if len(positive) >= 2 else None
    if adi is None:
        classification = "All zero"
    elif cv2 is None:
        classification = "Insufficient positive observations"
    elif adi < 1.32:
        classification = "Smooth" if cv2 < 0.49 else "Erratic"
    else:
        classification = "Intermittent" if cv2 < 0.49 else "Lumpy"
    return {"average_daily_demand": average, "nonzero_frequency": len(positive) / len(values),
            "zero_frequency": 1 - len(positive) / len(values), "daily_stddev": std,
            "daily_cv": std / average if average else None, "adi": adi,
            "positive_cv2": cv2, "segment": segment, "classification": classification}


def stratified_select(frame, count, seed):
    """Round-robin over observed joint strata, randomizing within strata only."""
    if count < 1 or count > len(frame):
        raise ValueError("Requested cohort is outside the eligible pool.")
    columns = ["category", "state", "segment", "classification"]
    if frame[columns + ["product_id", "store_id"]].isna().any().any():
        raise ValueError("Selection metadata must be complete.")
    if frame.duplicated(["product_id", "store_id"]).any():
        raise ValueError("Duplicate candidate pairs.")
    shuffled = frame.sample(frac=1, random_state=seed).copy()
    shuffled["stratum_rank"] = shuffled.groupby(columns, sort=True).cumcount()
    return shuffled.sort_values(["stratum_rank", *columns, "product_id", "store_id"]).head(count).drop(
        columns="stratum_rank").reset_index(drop=True)


def summarize(predictions, group_columns):
    """Pool errors after optional prior aggregation; no fold percentage averaging."""
    def calculate(group):
        error = group.prediction - group.sales_quantity
        total = group.sales_quantity.abs().sum()
        return pd.Series({"rows": len(group), "mae": error.abs().mean(),
                          "rmse": float(np.sqrt((error ** 2).mean())),
                          "wape": 100 * error.abs().sum() / total if total else np.nan,
                          "bias": error.mean()})
    return predictions.groupby(group_columns, dropna=False, sort=True).apply(
        calculate, include_groups=False).reset_index()


def aggregate_level(predictions, dimensions):
    keys = ["method", "origin", "date", *dimensions]
    return predictions.groupby(keys, dropna=False, as_index=False)[
        ["sales_quantity", "prediction"]
    ].sum()
