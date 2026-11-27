"""Research-only hurdle forecasts and leakage-safe pooled direct training."""

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor

from src.decisionos.ml.train import FEATURE_COLUMNS


class HurdleModel:
    def __init__(self, seed=42, estimators=60):
        self.classifier = LGBMClassifier(n_estimators=estimators, random_state=seed, n_jobs=2, verbosity=-1)
        self.quantity = LGBMRegressor(n_estimators=estimators, random_state=seed, n_jobs=2, verbosity=-1)
        self.probability = None
        self.size = None

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        occurred = y > 0
        if occurred.all() or not occurred.any():
            self.probability = float(occurred[0])
        else:
            self.classifier.fit(X, occurred.astype(int))
        if occurred.any():
            self.quantity.fit(X.loc[occurred], y[occurred])
        else:
            self.size = 0.0
        return self

    def predict(self, X):
        prob = (np.full(len(X), self.probability) if self.probability is not None
                else self.classifier.predict_proba(X)[:, 1])
        qty = np.full(len(X), self.size) if self.size is not None else self.quantity.predict(X)
        return np.maximum(prob * np.maximum(qty, 0), 0)


def direct_training(featured, stride=7, horizon=28):
    """Snapshot features once, and only use targets within the input training frame."""
    rows = []
    for _, group in featured.groupby(["product_id", "store_id"], sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        for index in range(0, len(group) - horizon + 1, stride):
            base = group.loc[index, FEATURE_COLUMNS].to_dict()
            for lead in range(1, horizon + 1):
                row = dict(base)
                row["lead"] = lead
                row["target"] = group.loc[index + lead - 1, "sales_quantity"]
                rows.append(row)
    return pd.DataFrame(rows)


def direct_forecast(model, train):
    """Build all 28 predictions from each pair's single origin snapshot."""
    from src.decisionos.ml.forecast import recursive_forecast

    class Capture:
        def predict(self, frame):
            self.frame = frame.copy()
            return np.zeros(len(frame))
    capture = Capture()
    origin = train.date.max()
    recursive_forecast(capture, train, [origin + pd.Timedelta(days=1)])
    pairs = train[["product_id", "store_id"]].drop_duplicates().sort_values(
        ["product_id", "store_id"]).reset_index(drop=True)
    snapshots = pd.concat([capture.frame.assign(lead=lead) for lead in range(1, 29)], ignore_index=True)
    predictions = np.maximum(model.predict(snapshots[FEATURE_COLUMNS + ["lead"]]), 0)
    rows = []
    for lead in range(1, 29):
        for pair, prediction in zip(pairs.itertuples(index=False),
                                    predictions[(lead - 1)*len(pairs):lead*len(pairs)]):
            rows.append({"product_id": pair.product_id, "store_id": pair.store_id,
                         "date": origin + pd.Timedelta(days=lead), "prediction": prediction})
    return pd.DataFrame(rows)
