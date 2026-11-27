"""Deterministic multi-step reference forecasts for nonnegative demand."""

import numpy as np


def baseline_forecast(history, horizon, method, window=28, alpha=0.1, beta=0.1):
    values = np.asarray(history, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("History must be a nonempty finite nonnegative vector.")
    if horizon < 1 or window < 1 or not 0 < alpha <= 1 or not 0 < beta <= 1:
        raise ValueError("Invalid horizon, window, or smoothing parameter.")
    if method == "zero":
        return np.zeros(horizon)
    if method == "mean":
        forecast = values.mean()
    elif method == "naive":
        forecast = values[-1]
    elif method == "moving_average":
        forecast = values[-window:].mean()
    elif method in ("seasonal_7", "seasonal_28"):
        period = int(method.split("_")[1])
        if len(values) < period:
            raise ValueError("Insufficient history for seasonal forecast.")
        return np.resize(values[-period:], horizon)
    elif method in ("croston", "sba", "tsb"):
        nonzero = np.flatnonzero(values > 0)
        if not len(nonzero):
            return np.zeros(horizon)
        first = nonzero[0]
        size = values[first]
        if method == "tsb":
            probability = 1 / (first + 1)
            for value in values[first + 1:]:
                occurrence = float(value > 0)
                probability += beta * (occurrence - probability)
                if occurrence:
                    size += alpha * (value - size)
            forecast = size * probability
        else:
            interval = first + 1
            last = first
            for index in nonzero[1:]:
                size += alpha * (values[index] - size)
                interval += alpha * (index - last - interval)
                last = index
            forecast = size / interval
            if method == "sba":
                forecast *= 1 - alpha / 2
    else:
        raise ValueError(f"Unknown baseline: {method}")
    return np.full(horizon, forecast, dtype=float)
