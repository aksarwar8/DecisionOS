"""Strict metrics for chronological research comparisons."""

import numpy as np


def score(actual, predicted, training):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    training = np.asarray(training, dtype=float)
    if (actual.ndim != 1 or predicted.shape != actual.shape or not actual.size
            or training.ndim != 1 or not training.size
            or not all(np.isfinite(x).all() for x in (actual, predicted, training))):
        raise ValueError("Inputs must be finite, nonempty, aligned vectors.")
    error = predicted - actual
    denominator = np.abs(actual).sum()
    scale = np.mean(np.diff(training) ** 2) if len(training) > 1 else 0.0
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "wape": float(100 * np.abs(error).sum() / denominator) if denominator else None,
        "rmsse": float(np.sqrt(np.mean(error ** 2) / scale)) if scale > 0 else None,
        "bias": float(np.mean(error)),
        "rows": len(actual),
    }
