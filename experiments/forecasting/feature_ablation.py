"""Run bounded research feature ablations using an existing cohort manifest."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sqlalchemy import text

from src.decisionos.data.extract import get_engine
from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.evaluation.backtest import rolling_windows
from src.decisionos.evaluation.experimental_features import (
    CATEGORICAL, FAMILIES, VERSION, columns, feature_row, fit_encodings,
)

CONFIGS = {
    "A_canonical": ["canonical"],
    "B_demand": ["canonical", "advanced_demand", "intermittency"],
    "C_calendar": ["canonical", "advanced_demand", "intermittency", "calendar_events"],
    "D_price_snap": ["canonical", "advanced_demand", "intermittency", "calendar_events", "snap", "pricing"],
    "E_categorical": ["canonical", "categorical_metadata"],
    "F_combined": list(FAMILIES),
}


def read_inputs(cohort, folds):
    engine = get_engine()
    query = text("""
        SELECT s.product_id,s.store_id,c.date,s.sales_quantity
        FROM unnest(CAST(:products AS integer[]),CAST(:stores AS integer[])) p(product_id,store_id)
        JOIN sales s ON s.product_id=p.product_id AND s.store_id=p.store_id
        JOIN calendar c ON c.id=s.calendar_id
        WHERE c.date BETWEEN :start AND :end ORDER BY s.product_id,s.store_id,c.date
    """)
    price_query = text("""
        SELECT q.product_id,q.store_id,q.wm_yr_wk,q.sell_price,w.week_end
        FROM unnest(CAST(:products AS integer[]),CAST(:stores AS integer[])) p(product_id,store_id)
        JOIN sell_prices q ON q.product_id=p.product_id AND q.store_id=p.store_id
        JOIN (SELECT wm_yr_wk, MAX(date) AS week_end FROM calendar GROUP BY wm_yr_wk) w
          ON w.wm_yr_wk=q.wm_yr_wk
        WHERE w.week_end BETWEEN :start AND :end
        ORDER BY q.product_id,q.store_id,w.week_end
    """)
    params = {"products": cohort.product_id.tolist(), "stores": cohort.store_id.tolist(),
              "start": (min(x[0] for x in folds) - pd.Timedelta(days=90)).date(),
              "end": max(x[3] for x in folds).date()}
    with engine.connect() as conn:
        conn.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        product_metadata = pd.read_sql(text("SELECT id AS product_id, department FROM products WHERE id = ANY(:ids)"), conn, params={"ids": cohort.product_id.tolist()})
        sales = pd.read_sql(query, conn, params=params)
        calendar = pd.read_sql(text("""SELECT date,wm_yr_wk,event_name_1,event_name_2,
                                     event_type_1,event_type_2,snap_ca,snap_tx,snap_wi
                                     FROM calendar WHERE date BETWEEN :start AND :end ORDER BY date"""),
                               conn, params=params)
        prices = pd.read_sql(price_query, conn, params=params)
    engine.dispose()
    for frame, field in ((sales, "date"), (calendar, "date"), (prices, "week_end")):
        frame[field] = pd.to_datetime(frame[field])
    if calendar.date.duplicated().any() or prices.duplicated(["product_id", "store_id", "wm_yr_wk"]).any():
        raise ValueError("Calendar dates and product-store-week prices must be unique.")
    if prices.sell_price.isna().any() or (prices.sell_price < 0).any():
        raise ValueError("Price records must be nonnegative and non-null.")
    return sales, calendar, prices, product_metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", default="research_output/stratified_60/cohort.json")
    parser.add_argument("--output", default="research_output/feature_ablation_v1")
    parser.add_argument("--pairs", type=int, default=60)
    parser.add_argument("--mlflow", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.pairs <= 60:
        parser.error("Limit is 60 pairs.")
    cohort = pd.read_json(args.cohort).head(args.pairs)
    if cohort.duplicated(["product_id", "store_id"]).any():
        raise ValueError("Cohort contains duplicate pairs.")
    folds = list(rolling_windows(["2015-04-30", "2015-07-31", "2015-10-31"], 365, 28))
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Choose a new output directory to preserve previous experiments.")
    output.mkdir(parents=True)
    sales, calendar, prices, product_metadata = read_inputs(cohort, folds)
    cohort = cohort.merge(product_metadata, on="product_id", validate="many_to_one")
    calendar_map = calendar.set_index("date").to_dict("index")
    sales_map = dict(tuple(sales.groupby(["product_id", "store_id"])))
    prices_map = dict(tuple(prices.groupby(["product_id", "store_id"])))
    empty_quotes = prices.iloc[:0]
    predictions, timings, importances, score_rows = [], [], [], []
    cohort.to_json(output / "cohort.json", orient="records", indent=2)
    (output / "config.json").write_text(json.dumps(
        {"version": VERSION, "configs": CONFIGS, "feature_lists": {k: columns(v) for k, v in CONFIGS.items()},
         "seed": 42, "trees": 100, "warmup": 90, "origins": [str(f[1].date()) for f in folds]}, indent=2),
        encoding="utf-8")
    for start, origin, first, end in folds:
        before = time.perf_counter()
        train = []
        histories = {}
        actual_rows = []
        metadata_frame = cohort.copy()
        for field in ("event_name_1", "event_name_2", "event_type_1", "event_type_2"):
            metadata_frame[field] = None
        encodings = fit_encodings(metadata_frame)
        for field in ("event_name_1", "event_name_2", "event_type_1", "event_type_2"):
            vals = calendar.loc[calendar.date.between(start, origin), field].dropna().unique()
            encodings[field] = {value: i for i, value in enumerate(sorted(vals))}
        for pair in cohort.to_dict("records"):
            key = (pair["product_id"], pair["store_id"])
            group = sales_map.get(key)
            if group is None:
                raise ValueError(f"Missing requested pair {key}")
            history = group[group.date.between(start, origin)].sort_values("date")
            actual = group[group.date.between(first, end)].sort_values("date")
            validate_historical_sales(history)
            validate_historical_sales(actual)
            if len(history) != 365 or len(actual) != 28:
                raise ValueError(f"Incomplete matched history for {key}")
            values = history.sales_quantity.to_numpy(dtype=float)
            histories[key] = values.tolist()
            quotes = prices_map.get(key, empty_quotes)
            for i in range(90, len(history)):
                date = history.date.iloc[i]
                row = feature_row(values[:i], date, *key, calendar_map[date], pair, encodings,
                                  quotes, date)
                row["target"] = values[i]
                train.append(row)
            actual_rows.append(actual)
        train = pd.DataFrame(train)
        actual = pd.concat(actual_rows)
        preparation = time.perf_counter() - before
        fold_predictions = []
        for label, families in CONFIGS.items():
            features = columns(families)
            categorical = [x for x in CATEGORICAL if x in features] if label in ("E_categorical", "F_combined") else []
            model = LGBMRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=2, verbosity=-1)
            before = time.perf_counter()
            model.fit(train[features], train.target, categorical_feature=categorical)
            fit_seconds = time.perf_counter() - before
            importance = model.booster_
            for name, gain, split in zip(features, importance.feature_importance("gain"),
                                         importance.feature_importance("split")):
                importances.append({"origin": str(origin.date()), "config": label,
                                    "feature": name, "gain": float(gain), "split": int(split)})
            states = {key: list(values) for key, values in histories.items()}
            before = time.perf_counter()
            rows = []
            for date in pd.date_range(first, end):
                X = []
                for pair in cohort.to_dict("records"):
                    key = (pair["product_id"], pair["store_id"])
                    X.append(feature_row(states[key], date, *key, calendar_map[date], pair, encodings,
                                         prices_map.get(key, empty_quotes), origin + pd.Timedelta(days=1)))
                predicted = np.maximum(model.predict(pd.DataFrame(X)[features]), 0)
                for pair, value in zip(cohort.to_dict("records"), predicted):
                    key = (pair["product_id"], pair["store_id"])
                    states[key].append(float(value))
                    rows.append({"product_id": key[0], "store_id": key[1], "date": date,
                                 "prediction": value})
            elapsed = time.perf_counter() - before
            forecast = pd.DataFrame(rows)
            joined = actual.merge(forecast, on=["product_id", "store_id", "date"], validate="one_to_one")
            if len(joined) != len(actual) or len(joined) != len(forecast):
                raise ValueError("Predictions and actual observations do not match.")
            joined = joined.merge(cohort, on=["product_id", "store_id"], validate="many_to_one")
            joined["method"] = label
            joined["origin"] = origin
            fold_predictions.append(joined)
            timings.append({"origin": str(origin.date()), "config": label, "features": len(features),
                            "preparation_seconds_shared": preparation, "training_seconds": fit_seconds,
                            "inference_seconds": elapsed})
            for (product, store), frame in joined.groupby(["product_id", "store_id"]):
                from src.decisionos.evaluation.metrics import score
                history = histories[(product, store)]
                for horizon in (7, 14, 28):
                    metric = score(frame.sales_quantity.iloc[:horizon], frame.prediction.iloc[:horizon], history)
                    score_rows.append({"origin": str(origin.date()), "method": label, "product_id": product,
                                       "store_id": store, "horizon": horizon, **metric})
        predictions.extend(fold_predictions)
        pd.concat(predictions).to_csv(output / "predictions.csv", index=False)
        pd.DataFrame(timings).to_csv(output / "timings.csv", index=False)
        pd.DataFrame(importances).to_csv(output / "importance.csv", index=False)
        pd.DataFrame(score_rows).to_csv(output / "series_metrics.csv", index=False)
    if args.mlflow:
        import mlflow
        from src.decisionos.config import get_settings
        mlflow.set_tracking_uri(get_settings().resolve_tracking_uri())
        mlflow.set_experiment("DecisionOS-feature-ablation-research")
        with mlflow.start_run(run_name="v1.4.2-feature-ablation") as run:
            mlflow.log_params({"feature_version": VERSION, "pairs": args.pairs, "seed": 42,
                               "trees": 100, "history_days": 365, "warmup": 90})
            mlflow.log_artifacts(str(output), artifact_path="research")
            print("MLflow experiment", run.info.experiment_id, "run", run.info.run_id)
    print("Completed", len(folds), "folds and", len(CONFIGS), "configurations.")


if __name__ == "__main__":
    main()
