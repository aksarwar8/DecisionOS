"""Versioned research-only forecasting features, shared by training and inference."""

import numpy as np
import pandas as pd

from src.decisionos.ml.train import FEATURE_COLUMNS

VERSION = "research-v1"
FAMILIES = {
    "canonical": FEATURE_COLUMNS,
    "advanced_demand": ["lag_1", "lag_2", "lag_56", "lag_90", "mean_14", "mean_56",
                        "std_28", "min_28", "max_28", "ewm_28", "momentum_7_28", "ratio_7_28"],
    "intermittency": ["nonzero_28", "zero_90", "days_since_nonzero", "adi_90",
                     "positive_mean_90", "positive_cv2_90"],
    "calendar_events": ["quarter", "dow_sin", "dow_cos", "month_sin", "month_cos",
                        "event_1", "event_2", "event_type_1_code", "event_type_2_code",
                        "event_name_1_code", "event_name_2_code"],
    "snap": ["snap_state"],
    "pricing": ["price_last", "price_previous", "price_ratio", "price_change",
                "price_std", "price_available", "price_recent_change"],
    "categorical_metadata": ["category_code", "department_code", "state_code"],
}
CATEGORICAL = ["product_id", "store_id", "category_code", "department_code", "state_code",
               "event_type_1_code", "event_type_2_code", "event_name_1_code", "event_name_2_code"]


def columns(families):
    if not families or families[0] != "canonical" or len(set(families)) != len(families):
        raise ValueError("Families must start with canonical and be unique.")
    if any(family not in FAMILIES for family in families):
        raise ValueError("Unknown feature family.")
    return [name for family in families for name in FAMILIES[family]]


def fit_encodings(frame):
    fields = ("category", "department", "state", "event_name_1", "event_name_2",
              "event_type_1", "event_type_2")
    return {field: {value: index for index, value in enumerate(sorted(frame[field].dropna().unique()))}
            for field in fields}


def code(value, mapping):
    return mapping.get(value, -1) if pd.notna(value) else -1


def historical_prices(quotes, cutoff):
    """Use only quotes whose complete week ended strictly before cutoff."""
    eligible = quotes[quotes["week_end"] < pd.Timestamp(cutoff)].tail(8)
    if eligible.empty:
        return dict.fromkeys(FAMILIES["pricing"], np.nan) | {"price_available": 0}
    values = eligible["sell_price"].to_numpy(dtype=float)
    last = values[-1]
    previous = values[-2] if len(values) > 1 else np.nan
    return {"price_last": last, "price_previous": previous,
            "price_ratio": last / values.mean() if values.mean() else np.nan,
            "price_change": (last - previous) / previous if previous > 0 else np.nan,
            "price_std": values.std(), "price_available": 1,
            "price_recent_change": float(last != previous) if np.isfinite(previous) else np.nan}


def feature_row(values, date, product_id, store_id, calendar, metadata, encodings, prices, price_cutoff):
    values = np.asarray(values, dtype=float)
    if len(values) < 90 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("At least 90 finite nonnegative history values are required.")
    day = pd.Timestamp(date)
    last7, last28, last90 = values[-7:], values[-28:], values[-90:]
    positive = last90[last90 > 0]
    offsets = np.flatnonzero(last90 > 0)
    mean7, mean28 = last7.mean(), last28.mean()
    recent = pd.Series(last90).ewm(span=28, adjust=False).mean().iloc[-1]
    row = {"product_id": product_id, "store_id": store_id, "year": day.year,
           "month": day.month, "day": day.day, "day_of_week": day.dayofweek,
           "week_of_year": int(day.isocalendar().week), "is_weekend": int(day.dayofweek >= 5),
           "lag_7": values[-7], "lag_14": values[-14], "lag_28": values[-28],
           "rolling_mean_7": mean7, "rolling_mean_28": mean28,
           "rolling_std_7": last7.std(ddof=1),
           "lag_1": values[-1], "lag_2": values[-2], "lag_56": values[-56], "lag_90": values[-90],
           "mean_14": values[-14:].mean(), "mean_56": values[-56:].mean(),
           "std_28": last28.std(ddof=1), "min_28": last28.min(), "max_28": last28.max(),
           "ewm_28": recent, "momentum_7_28": mean7 - mean28,
           "ratio_7_28": mean7 / mean28 if mean28 else np.nan,
           "nonzero_28": np.count_nonzero(last28) / 28, "zero_90": np.count_nonzero(last90 == 0) / 90,
           "days_since_nonzero": 90 - offsets[-1] if len(offsets) else np.nan,
           "adi_90": 90 / len(positive) if len(positive) else np.nan,
           "positive_mean_90": positive.mean() if len(positive) else np.nan,
           "positive_cv2_90": (positive.std() / positive.mean()) ** 2 if len(positive) >= 2 else np.nan,
           "quarter": day.quarter, "dow_sin": np.sin(2 * np.pi * day.dayofweek / 7),
           "dow_cos": np.cos(2 * np.pi * day.dayofweek / 7),
           "month_sin": np.sin(2 * np.pi * (day.month - 1) / 12),
           "month_cos": np.cos(2 * np.pi * (day.month - 1) / 12),
           "event_1": int(pd.notna(calendar["event_name_1"])),
           "event_2": int(pd.notna(calendar["event_name_2"])),
           "snap_state": calendar.get("snap_" + str(metadata["state"]).lower(), np.nan)}
    for slot in (1, 2):
        for kind in ("event_name", "event_type"):
            key = f"{kind}_{slot}"
            row[key + "_code"] = code(calendar[key], encodings[key])
    for field in ("category", "department", "state"):
        row[field + "_code"] = code(metadata[field], encodings[field])
    row.update(historical_prices(prices, price_cutoff))
    return row
