"""Interpretable past-only anomaly flags for one daily sales series."""

import numpy as np

from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales


def detect_demand_anomalies(history, window=28, threshold=3.5):
    if window < 14 or threshold <= 0:
        raise ValueError("Invalid anomaly parameters.")
    history = history.assign(date=validate_historical_sales(history)).sort_values("date")
    if len(history[["product_id", "store_id"]].drop_duplicates()) != 1:
        raise HistoricalSalesError("Anomaly analysis requires one product-store pair.")
    values = history.sales_quantity.to_numpy(dtype=float)
    rows = []
    for index in range(window, len(values)):
        previous = values[index-window:index]
        reference = float(np.median(previous))
        mad = float(np.median(np.abs(previous-reference)))
        observed = float(values[index])
        score = 0.6745 * (observed-reference) / mad if mad > 0 else None
        distance = observed - reference
        # The zero-MAD rule needs an absolute difference as well as a proportional change.
        spike = (score is not None and score > threshold) or (mad == 0 and distance >= max(3, reference))
        drop = ((score is not None and score < -threshold and observed > 0)
                or (mad == 0 and reference >= 3 and 0 < observed <= reference * 0.25))
        zero_run = (observed == 0 and index >= 14 and np.all(values[index-13:index+1] == 0)
                    and values[index-14] > 0 and np.count_nonzero(previous) / window >= 0.2)
        kind = "spike" if spike else "demand_drop" if drop else "prolonged_zero" if zero_run else None
        if kind:
            severity = "high" if (score is not None and abs(score) >= 7) or zero_run else "medium"
            row = history.iloc[index]
            rows.append({"date": row.date.date(), "product_id": int(row.product_id), "store_id": int(row.store_id),
                         "type": kind, "severity": severity, "risk_score": 80 if severity == "high" else 50,
                         "observed": observed, "reference": reference,
                         "evidence": {"prior_days": window, "median": reference, "mad": mad,
                                      "modified_z": score, "zero_run_days": 14 if zero_run else None}})
    return rows
