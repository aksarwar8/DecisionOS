"""Controlled synthetic interval and anomaly checks; no external services."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.decisionos.ml.strategies import rolling_intervals
from src.decisionos.monitoring.anomalies import detect_demand_anomalies


def main():
    rng = np.random.default_rng(42)
    values = rng.poisson(2, 150)
    frame = pd.DataFrame({"product_id": 1, "store_id": 1,
                          "date": pd.date_range("2020-01-01", periods=len(values)),
                          "sales_quantity": values})
    train, actual = frame.iloc[:122].tail(90), frame.iloc[122:]
    output = {}
    for coverage in (0.8, 0.95):
        intervals, n = rolling_intervals(train, 28, "tsb", coverage)
        low = np.array([item["lower"] for item in intervals])
        high = np.array([item["upper"] for item in intervals])
        target = actual.sales_quantity.to_numpy()
        alpha = 1 - coverage
        interval_score = (high-low + 2/alpha*(low-target)*(target < low)
                          + 2/alpha*(target-high)*(target > high))
        output[str(coverage)] = {"coverage": float(np.mean((low <= target) & (target <= high))),
                                 "mean_width": float(np.mean(high-low)),
                                 "interval_score": float(np.mean(interval_score)),
                                 "calibration_origins": n, "evaluation_rows": len(target)}
    sample = np.full(150, 2)
    indices = [40, 80, 120]
    sample[indices] = 20
    injected = frame.assign(sales_quantity=sample)
    flagged = detect_demand_anomalies(injected)
    hits = {item["date"] for item in flagged}
    truth = {injected.date.iloc[i].date() for i in indices}
    tp = len(hits & truth)
    precision = tp / len(hits) if hits else 0
    recall = tp / len(truth)
    output["anomaly"] = {"injected_spikes": len(truth), "flags": len(hits),
                         "true_positives": tp, "precision": precision, "recall": recall,
                         "f1": 2*precision*recall/(precision+recall) if precision+recall else 0}
    destination = Path("research_output/predictive_checks")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "synthetic_metrics.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
