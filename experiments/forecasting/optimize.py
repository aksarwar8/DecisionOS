"""Bounded development and locked independent holdout comparison."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sqlalchemy import text

from src.decisionos.data.extract import get_engine
from src.decisionos.data.transform import transform_sales
from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.evaluation.backtest import rolling_windows
from src.decisionos.evaluation.characterize import aggregate_level, characterize, summarize
from src.decisionos.evaluation.metrics import score
from src.decisionos.evaluation.optimization import HurdleModel, direct_forecast, direct_training
from src.decisionos.ml.baselines import baseline_forecast
from src.decisionos.ml.dataset import prepare_ml_dataset
from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.train import FEATURE_COLUMNS

BASELINES = {**{f"tsb_{a}": ("tsb", a, 28) for a in (0.05, 0.1, 0.2, 0.3)},
             **{f"sba_{a}": ("sba", a, 28) for a in (0.05, 0.1, 0.2, 0.3)},
             **{f"moving_{w}": ("moving_average", 0.1, w) for w in (7, 14, 28, 56, 90)},
             "zero": ("zero", 0.1, 28)}
MODELS = {"lgb_l2": {"objective": "regression"},
          "lgb_l1": {"objective": "regression_l1"},
          "lgb_poisson": {"objective": "poisson"},
          "lgb_tweedie": {"objective": "tweedie", "tweedie_variance_power": 1.2},
          "lgb_small": {"objective": "regression", "num_leaves": 15, "min_child_samples": 50}}


def select_cohort(mode, engine, size, seed):
    development = pd.read_json("research_output/stratified_60/cohort.json")
    if mode == "dev":
        return development.head(size).copy()
    with engine.connect() as connection:
        catalog = pd.read_sql(text("""SELECT p.id AS product_id,s.id AS store_id,p.category,s.state,
                                      s.store_id AS store_code FROM products p CROSS JOIN stores s
                                      ORDER BY p.id,s.id"""), connection)
    existing = set(zip(development.product_id, development.store_id))
    catalog = catalog[[tuple(pair) not in existing for pair in
                       zip(catalog.product_id, catalog.store_id)]]
    return catalog.sample(n=size, random_state=seed).sort_values(["product_id", "store_id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("dev", "holdout"))
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lock")
    parser.add_argument("--mlflow", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.pairs <= 60:
        parser.error("Pair limit is 60.")
    if args.mode == "holdout" and not args.lock:
        parser.error("Holdout requires a locked development selection.")
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Output directory already exists.")
    output.mkdir(parents=True)
    engine = get_engine()
    cohort = select_cohort(args.mode, engine, args.pairs, args.seed)
    cohort.to_json(output / "cohort.json", orient="records", indent=2)
    origins = ["2015-04-30", "2015-07-31", "2015-10-31"] if args.mode == "dev" else ["2016-03-27"]
    folds = list(rolling_windows(origins, 365, 28))
    with engine.connect() as connection:
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        sales = pd.read_sql(text("""
            SELECT s.product_id,s.store_id,c.date,s.sales_quantity
            FROM unnest(CAST(:products AS integer[]),CAST(:stores AS integer[])) p(product_id,store_id)
            JOIN sales s ON s.product_id=p.product_id AND s.store_id=p.store_id
            JOIN calendar c ON c.id=s.calendar_id
            WHERE c.date BETWEEN :start AND :end ORDER BY s.product_id,s.store_id,c.date
        """), connection, params={"products": cohort.product_id.tolist(), "stores": cohort.store_id.tolist(),
                                  "start": min(x[0] for x in folds).date(),
                                  "end": max(x[3] for x in folds).date()})
    engine.dispose()
    sales["date"] = pd.to_datetime(sales["date"])
    allowed = None if args.mode == "dev" else set(json.loads(Path(args.lock).read_text(encoding="utf-8"))["methods"])
    all_predictions, all_scores, timings, exclusions = [], [], [], []
    for start, origin, first, end in folds:
        train_groups, actual_groups, profiles = [], [], []
        for pair in cohort.to_dict("records"):
            data = sales[(sales.product_id == pair["product_id"]) & (sales.store_id == pair["store_id"])]
            train = data[data.date.between(start, origin)]
            actual = data[data.date.between(first, end)]
            try:
                validate_historical_sales(train)
                validate_historical_sales(actual)
                if len(train) != 365 or len(actual) != 28:
                    raise ValueError("Incomplete window")
            except ValueError as error:
                exclusions.append({"origin": str(origin.date()), "product_id": pair["product_id"],
                                   "store_id": pair["store_id"], "reason": str(error)})
                continue
            train_groups.append(train)
            actual_groups.append(actual)
            profiles.append({"product_id": pair["product_id"], "store_id": pair["store_id"],
                             **characterize(train.sales_quantity)})
        if not train_groups:
            raise ValueError("No valid series in fold.")
        train = pd.concat(train_groups)
        actual = pd.concat(actual_groups)
        dates = pd.date_range(first, end)
        methods = {}
        fold_times = {}
        for label, (method, alpha, window) in BASELINES.items():
            if allowed is not None and label not in allowed and label != "tsb_0.1":
                continue
            before = time.perf_counter()
            rows = []
            for group in train_groups:
                values = baseline_forecast(group.sales_quantity, 28, method, window=window,
                                           alpha=alpha, beta=alpha)
                rows.extend({"product_id": int(group.product_id.iloc[0]), "store_id": int(group.store_id.iloc[0]),
                             "date": date, "prediction": prediction} for date, prediction in zip(dates, values))
            methods[label] = pd.DataFrame(rows)
            fold_times[label] = (0.0, time.perf_counter() - before)
        before = time.perf_counter()
        featured = prepare_ml_dataset(transform_sales(train))
        prep_seconds = time.perf_counter() - before
        for label, params in MODELS.items():
            if allowed is not None and label not in allowed:
                continue
            model = LGBMRegressor(n_estimators=60, max_depth=15, random_state=42, n_jobs=2, verbosity=-1, **params)
            before = time.perf_counter()
            model.fit(featured[FEATURE_COLUMNS], featured.sales_quantity)
            training_time = time.perf_counter() - before
            before = time.perf_counter()
            methods[label] = recursive_forecast(model, train, dates.tolist())
            fold_times[label] = (training_time, time.perf_counter() - before)
        if allowed is None or "hurdle" in allowed:
            before = time.perf_counter()
            hurdle = HurdleModel().fit(featured[FEATURE_COLUMNS], featured.sales_quantity)
            training_time = time.perf_counter() - before
            before = time.perf_counter()
            methods["hurdle"] = recursive_forecast(hurdle, train, dates.tolist())
            fold_times["hurdle"] = (training_time, time.perf_counter() - before)
        if allowed is None or "direct" in allowed:
            before = time.perf_counter()
            direct_data = direct_training(featured)
            direct = LGBMRegressor(n_estimators=60, max_depth=15, random_state=42, n_jobs=2, verbosity=-1)
            direct.fit(direct_data[FEATURE_COLUMNS + ["lead"]], direct_data.target)
            training_time = time.perf_counter() - before
            before = time.perf_counter()
            methods["direct"] = direct_forecast(direct, train)
            fold_times["direct"] = (training_time, time.perf_counter() - before)
        # A pre-specified, interpretable routing hypothesis; no holdout tuning.
        if allowed is None or "adaptive" in allowed:
            required = {"tsb_0.1", "moving_28"}
            if not required <= methods.keys():
                raise ValueError("Adaptive policy requires tsb_0.1 and moving_28.")
            prof = pd.DataFrame(profiles)
            routes = prof[["product_id", "store_id", "classification"]]
            tsb = methods["tsb_0.1"].merge(routes, on=["product_id", "store_id"], validate="many_to_one")
            moving = methods["moving_28"].merge(routes, on=["product_id", "store_id"], validate="many_to_one")
            sparse = ["All zero", "Insufficient positive observations", "Intermittent", "Lumpy"]
            methods["adaptive"] = pd.concat([tsb[tsb.classification.isin(sparse)],
                                             moving[~moving.classification.isin(sparse)]])
            fold_times["adaptive"] = (0.0, fold_times["tsb_0.1"][1] + fold_times["moving_28"][1])
        fold_predictions = []
        for label, forecast in methods.items():
            joined = actual.merge(forecast[["product_id", "store_id", "date", "prediction"]],
                                  on=["product_id", "store_id", "date"], validate="one_to_one", how="outer",
                                  indicator=True)
            if not joined["_merge"].eq("both").all():
                raise ValueError(f"Forecast alignment failure for {label}.")
            joined = joined.drop(columns="_merge").merge(cohort[["product_id", "store_id", "category", "state"]],
                                                         on=["product_id", "store_id"], validate="many_to_one")
            joined = joined.merge(pd.DataFrame(profiles)[["product_id", "store_id", "segment", "classification"]],
                                  on=["product_id", "store_id"], validate="many_to_one")
            joined["method"] = label
            joined["origin"] = origin
            fold_predictions.append(joined)
            for group in train_groups:
                product, store = int(group.product_id.iloc[0]), int(group.store_id.iloc[0])
                subset = joined[(joined.product_id == product) & (joined.store_id == store)].sort_values("date")
                for h in (7, 14, 28):
                    metric = score(subset.sales_quantity.iloc[:h], subset.prediction.iloc[:h], group.sales_quantity)
                    all_scores.append({"origin": str(origin.date()), "method": label, "product_id": product,
                                       "store_id": store, "horizon": h, **metric})
            timings.append({"origin": str(origin.date()), "method": label, "training_seconds": fold_times[label][0],
                            "prediction_seconds": fold_times[label][1], "shared_feature_seconds": prep_seconds})
        all_predictions.extend(fold_predictions)
        predictions = pd.concat(all_predictions, ignore_index=True)
        predictions.to_csv(output / "predictions.csv", index=False)
        pd.DataFrame(all_scores).to_csv(output / "series_metrics.csv", index=False)
        pd.DataFrame(timings).to_csv(output / "timings.csv", index=False)
        (output / "exclusions.json").write_text(json.dumps(exclusions, indent=2), encoding="utf-8")
    for name, keys in (("overall", ["method"]), ("segment", ["method", "segment"]),
                       ("classification", ["method", "classification"]), ("origin", ["method", "origin"])):
        summarize(predictions, keys).to_csv(output / f"summary_{name}.csv", index=False)
    predictions["step"] = (pd.to_datetime(predictions.date) - pd.to_datetime(predictions.origin)).dt.days
    horizon = pd.concat([predictions[predictions.step <= h].assign(horizon=h) for h in (7, 14, 28)])
    summarize(horizon, ["method", "horizon"]).to_csv(output / "summary_horizon.csv", index=False)
    hierarchical = []
    for level, dimensions in {"pair": ["product_id", "store_id"], "product": ["product_id"],
                              "store": ["store_id"], "category": ["category"], "state": ["state"],
                              "cohort_total": []}.items():
        value = summarize(aggregate_level(predictions, dimensions), ["method"])
        value["level"] = level
        hierarchical.append(value)
    pd.concat(hierarchical).to_csv(output / "summary_hierarchy.csv", index=False)
    pd.DataFrame(all_scores).groupby(["method", "horizon"]).agg(
        mean_rmsse=("rmsse", "mean"), valid=("rmsse", "count"), total=("rmsse", "size")
    ).assign(undefined=lambda x: x.total-x.valid).to_csv(output / "summary_rmsse.csv")
    config = vars(args) | {"origins": origins, "training_days": 365, "horizon": 28,
                           "baseline_grid": BASELINES, "model_grid": MODELS}
    (output / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if args.mlflow:
        import mlflow
        from src.decisionos.config import get_settings
        mlflow.set_tracking_uri(get_settings().resolve_tracking_uri())
        mlflow.set_experiment("DecisionOS-optimization-research")
        with mlflow.start_run(run_name=f"v1.4.3-{args.mode}") as run:
            mlflow.log_params({key: str(value) for key, value in vars(args).items()})
            for row in summarize(predictions, ["method"]).itertuples():
                for name in ("mae", "rmse", "wape", "bias"):
                    value = getattr(row, name)
                    if np.isfinite(value):
                        mlflow.log_metric(f"{row.method}_{name}", value)
            mlflow.set_tag("source_revision", subprocess.run(["git", "rev-parse", "HEAD"], text=True,
                                                              capture_output=True, check=False).stdout.strip())
            mlflow.set_tag("source_status", "uncommitted")
            mlflow.log_artifacts(str(output), artifact_path="results")
            print("MLflow", run.info.experiment_id, run.info.run_id)
    print(summarize(predictions, ["method"])[["method", "mae", "rmse", "wape", "bias"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
