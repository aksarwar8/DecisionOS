"""Deployable deterministic forecast strategies."""

import numpy as np
import pandas as pd

from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales
from src.decisionos.ml.baselines import baseline_forecast
from src.decisionos.ml.hybrid import hybrid_forecast

METHODS = {
    "hybrid": {"label": "Registered hybrid", "status": "established", "configuration": "registered candidate alias",
               "limitation": "Recursive predictions can accumulate error."},
    "tsb": {"label": "TSB", "status": "experimental", "configuration": "alpha=0.1, beta=0.1",
            "limitation": "Constant forecast from the selected history; no calendar covariates."},
    "moving_average": {"label": "Moving average", "status": "experimental", "configuration": "window=28",
                       "limitation": "Constant forecast from the recent 28 days."},
    "seasonal_naive": {"label": "Seasonal naive", "status": "experimental", "configuration": "period=7",
                       "limitation": "Repeats the last recorded week."},
}


def forecast_history(history, horizon, method="hybrid", model=None):
    if method not in METHODS or horizon not in (7, 14, 28):
        raise HistoricalSalesError("Unknown forecast method or unsupported horizon.")
    history = history.assign(date=validate_historical_sales(history)).sort_values(
        ["product_id", "store_id", "date"])
    groups = history.groupby(["product_id", "store_id"], sort=True)
    if groups.size().lt(28).any() or groups.date.max().nunique() != 1:
        raise HistoricalSalesError("Each series needs 28 observations and a common forecast origin.")
    origin = history.date.max()
    dates = pd.date_range(origin + pd.Timedelta(days=1), periods=horizon)
    if method == "hybrid":
        if model is None:
            raise ValueError("Hybrid forecasting requires a loaded model.")
        return hybrid_forecast(model, history, dates.tolist())
    rows = []
    for (product, store), group in groups:
        values = group.sales_quantity.to_numpy(dtype=float)
        segment = ("Zero average" if values.mean() == 0 else "Low demand" if values.mean() <= 1
                   else "Medium demand" if values.mean() <= 5 else "High demand")
        baseline = {"tsb": "tsb", "moving_average": "moving_average",
                    "seasonal_naive": "seasonal_7"}[method]
        predicted = baseline_forecast(values, horizon, baseline)
        rows.extend({"product_id": product, "store_id": store, "date": date,
                     "prediction": float(value), "demand_segment": segment, "selected_model": method}
                    for date, value in zip(dates, predicted))
    return pd.DataFrame(rows)


def rolling_intervals(history, horizon, method, coverage, model=None):
    """Pair-specific empirical absolute errors from nonoverlapping past origins."""
    if coverage not in (0.8, 0.95):
        raise HistoricalSalesError("Coverage must be 0.8 or 0.95.")
    history = history.assign(date=validate_historical_sales(history)).sort_values("date").reset_index(drop=True)
    if history[["product_id", "store_id"]].drop_duplicates().shape[0] != 1:
        raise HistoricalSalesError("Intervals require a single product-store pair.")
    errors = {step: [] for step in range(1, horizon + 1)}
    # Up to 90 historical daily origins provide a finite-sample rank for 95% coverage.
    for cutoff in range(28, len(history) - horizon + 1):
        prior = history.iloc[:cutoff]
        actual = history.iloc[cutoff:cutoff+horizon]
        forecast = forecast_history(prior, horizon, method, model)
        for step, (observed, predicted) in enumerate(zip(actual.sales_quantity, forecast.prediction), 1):
            errors[step].append(abs(float(observed) - float(predicted)))
    count = len(errors[1])
    rank = int(np.ceil((count + 1) * coverage))
    if count < 20 or rank > count:
        raise HistoricalSalesError("Insufficient calibration history for the requested coverage and horizon.")
    point = forecast_history(history, horizon, method, model)
    bounds = []
    for step, row in enumerate(point.itertuples(index=False), 1):
        radius = sorted(errors[step])[rank - 1]
        bounds.append({"date": row.date.date(), "prediction": row.prediction,
                       "lower": max(0.0, row.prediction - radius), "upper": row.prediction + radius})
    return bounds, count
