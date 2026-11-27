"""Run a bounded, reproducible exploratory comparison against PostgreSQL."""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.decisionos.data.extract import get_engine
from src.decisionos.data.transform import transform_sales
from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.evaluation.backtest import rolling_windows
from src.decisionos.evaluation.metrics import score
from src.decisionos.evaluation.characterize import characterize, stratified_select
from src.decisionos.ml.baselines import baseline_forecast
from src.decisionos.ml.dataset import prepare_ml_dataset
from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.hybrid import hybrid_forecast
from src.decisionos.ml.train import train_random_forest, FEATURE_COLUMNS, TARGET_COLUMN


METHODS = ("zero", "mean", "naive", "moving_average", "seasonal_7", "seasonal_28",
           "croston", "sba", "tsb", "random_forest", "hybrid")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=12, choices=range(1, 121))
    parser.add_argument("--pool", type=int, default=360)
    parser.add_argument("--lightgbm", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--training-days", type=int, default=365)
    parser.add_argument("--origins", nargs="+", default=["2015-04-30", "2015-07-31", "2015-10-31"])
    parser.add_argument("--horizon", type=int, default=28, choices=(7, 14, 28))
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--output", default="research_output")
    parser.add_argument("--mlflow", action="store_true", help="Log completed run to configured research tracking store")
    args = parser.parse_args()
    if not 28 <= args.training_days <= 1095 or not 1 <= args.trees <= 100 or not args.pairs <= args.pool <= 600:
        parser.error("training-days must be 28–1095 and trees 1–100")
    folds = list(rolling_windows(args.origins, args.training_days, args.horizon))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with engine.connect() as connection:
        catalog = pd.read_sql(text("""
            SELECT p.id AS product_id, s.id AS store_id, p.category, s.state, s.store_id AS store_code
            FROM products p CROSS JOIN stores s ORDER BY p.id, s.id
        """), connection)
        # Draw an inexpensive catalog pool before observing any sales.
        pool = catalog.sample(n=args.pool, random_state=args.seed).sort_values(["product_id", "store_id"])
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        query = text("""
            SELECT sales.product_id, sales.store_id, calendar.date, sales.sales_quantity
            FROM unnest(CAST(:products AS integer[]), CAST(:stores AS integer[]))
              AS selected(product_id, store_id)
            JOIN sales ON sales.product_id=selected.product_id AND sales.store_id=selected.store_id
            JOIN calendar ON calendar.id=sales.calendar_id
            WHERE calendar.date BETWEEN :start_date AND :end_date
            ORDER BY sales.product_id, sales.store_id, calendar.date
        """)
        earliest = min(folds, key=lambda item: item[1])
        initial = pd.read_sql(query, connection, params={
            "products": pool.product_id.tolist(), "stores": pool.store_id.tolist(),
            "start_date": earliest[0].date(), "end_date": earliest[1].date(),
        })
        initial["date"] = pd.to_datetime(initial["date"])
        characteristics = []
        pool_exclusions = []
        groups = dict(tuple(initial.groupby(["product_id", "store_id"])))
        for pair in pool.itertuples(index=False):
            group = groups.get((pair.product_id, pair.store_id))
            try:
                if group is None:
                    raise ValueError("No training history")
                validate_historical_sales(group)
                if len(group) != args.training_days or group.date.min() != earliest[0] or group.date.max() != earliest[1]:
                    raise ValueError("Incomplete initial training window")
                characteristics.append({"product_id": pair.product_id, "store_id": pair.store_id,
                                        **characterize(group.sales_quantity)})
            except ValueError as error:
                pool_exclusions.append({"product_id": pair.product_id, "store_id": pair.store_id,
                                        "reason": str(error)})
        eligible = pool.merge(pd.DataFrame(characteristics), on=["product_id", "store_id"])
        pool.to_json(output / "catalog_pool.json", orient="records", indent=2)
        cohort = stratified_select(eligible, args.pairs, args.seed)
        cohort.to_json(output / "cohort.json", orient="records", indent=2)
        (output / "pool_exclusions.json").write_text(json.dumps(pool_exclusions, indent=2), encoding="utf-8")
        history = pd.read_sql(query, connection, params={
            "products": cohort.product_id.tolist(), "stores": cohort.store_id.tolist(),
            "start_date": min(fold[0] for fold in folds).date(),
            "end_date": max(fold[3] for fold in folds).date(),
        })
    history["date"] = pd.to_datetime(history["date"])
    methods = (*METHODS, "lightgbm") if args.lightgbm else METHODS
    results = []
    series_scores = []
    fold_characteristics = []
    predictions = []
    exclusions = []
    for start, origin, first, end in folds:
        train_groups = []
        actual_groups = []
        for pair in cohort.itertuples(index=False):
            pair_data = history[(history.product_id == pair.product_id) & (history.store_id == pair.store_id)]
            train = pair_data[pair_data.date.between(start, origin)]
            actual = pair_data[pair_data.date.between(first, end)]
            try:
                validate_historical_sales(train)
                validate_historical_sales(actual)
                if len(train) != args.training_days or len(actual) != args.horizon:
                    raise ValueError("Incomplete training or evaluation window")
            except ValueError as error:
                exclusions.append({"origin": str(origin.date()), "product_id": pair.product_id,
                                   "store_id": pair.store_id, "reason": str(error)})
                continue
            train_groups.append(train)
            actual_groups.append(actual)
        if not train_groups:
            continue
        train = pd.concat(train_groups)
        actual = pd.concat(actual_groups)
        before = time.perf_counter()
        features = prepare_ml_dataset(transform_sales(train))
        model = train_random_forest(features, n_estimators=args.trees, random_state=args.seed)
        training_seconds = time.perf_counter() - before
        challenger = None
        challenger_seconds = 0.0
        if args.lightgbm:
            from lightgbm import LGBMRegressor
            before = time.perf_counter()
            challenger = LGBMRegressor(n_estimators=100, max_depth=15, random_state=args.seed,
                                      n_jobs=2, verbosity=-1)
            challenger.fit(features[FEATURE_COLUMNS], features[TARGET_COLUMN])
            challenger_seconds = time.perf_counter() - before
        fold_stats = pd.DataFrame([
            {"product_id": int(group.product_id.iloc[0]), "store_id": int(group.store_id.iloc[0]),
             **characterize(group.sales_quantity)} for group in train_groups
        ])
        fold_characteristics.extend(fold_stats.assign(origin=str(origin.date())).to_dict(orient="records"))
        pd.DataFrame(fold_characteristics).to_csv(output / "fold_characteristics.csv", index=False)
        dates = pd.date_range(first, end).tolist()
        for method in methods:
            before = time.perf_counter()
            if method in ("random_forest", "hybrid", "lightgbm"):
                forecast = (hybrid_forecast if method == "hybrid" else recursive_forecast)(
                    challenger if method == "lightgbm" else model, train, dates)
            else:
                rows = []
                for group in train_groups:
                    first_row = group.iloc[0]
                    values = baseline_forecast(group.sales_quantity, args.horizon, method)
                    rows.extend({"product_id": first_row.product_id, "store_id": first_row.store_id,
                                 "date": date, "prediction": value}
                                for date, value in zip(dates, values))
                forecast = pd.DataFrame(rows)
            duration = time.perf_counter() - before
            joined = actual.merge(forecast[["product_id", "store_id", "date", "prediction"]],
                                  on=["product_id", "store_id", "date"], validate="one_to_one")
            if len(joined) != len(actual) or len(joined) != len(forecast):
                raise ValueError("Forecast keys do not match actual observations.")
            joined = joined.merge(cohort, on=["product_id", "store_id"], validate="many_to_one")
            joined = joined.merge(fold_stats[["product_id", "store_id", "segment", "classification"]],
                                  on=["product_id", "store_id"], validate="many_to_one",
                                  suffixes=("_initial", ""))
            for group in train_groups:
                product = int(group.product_id.iloc[0])
                store = int(group.store_id.iloc[0])
                subset = joined[(joined.product_id == product) & (joined.store_id == store)]
                for horizon in (7, 14, 28):
                    if horizon <= args.horizon:
                        metric = score(subset.sales_quantity.iloc[:horizon], subset.prediction.iloc[:horizon],
                                       group.sales_quantity)
                        series_scores.append({"origin": str(origin.date()), "method": method,
                                              "product_id": product, "store_id": store,
                                              "horizon": horizon, **metric})
            joined["method"] = method
            joined["origin"] = str(origin.date())
            predictions.append(joined)
            metrics = score(joined.sales_quantity, joined.prediction, train.sales_quantity)
            # Per-series RMSSE cannot use a concatenated training series.
            metrics.pop("rmsse")
            results.append({"origin": str(origin.date()), "method": method,
                            "series": len(train_groups), "training_seconds": training_seconds
                            if method in ("random_forest", "hybrid") else challenger_seconds if method == "lightgbm" else 0,
                            "prediction_seconds": duration, **metrics})
        pd.DataFrame(series_scores).to_csv(output / "series_metrics.csv", index=False)
        pd.DataFrame(results).to_csv(output / "fold_metrics.csv", index=False)
        pd.concat(predictions).to_csv(output / "predictions.csv", index=False)
    (output / "exclusions.json").write_text(json.dumps(exclusions, indent=2), encoding="utf-8")
    (output / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    if not results:
        raise RuntimeError("No eligible series in any fold.")
    if args.mlflow:
        import mlflow

        from src.decisionos.config import get_settings

        settings = get_settings()
        mlflow.set_tracking_uri(settings.resolve_tracking_uri())
        mlflow.set_experiment("DecisionOS-forecast-research")
        with mlflow.start_run(run_name="bounded-rolling-benchmark"):
            mlflow.log_params({key: str(value) for key, value in vars(args).items()})
            all_predictions = pd.concat(predictions)
            for method, group in all_predictions.groupby("method"):
                pooled = score(group.sales_quantity, group.prediction, [0, 1])
                for metric in ("mae", "rmse", "wape", "bias"):
                    if pooled[metric] is not None:
                        mlflow.log_metric(f"{method}_{metric}", pooled[metric])
            mlflow.log_artifacts(str(output), artifact_path="research_results")
            import subprocess
            mlflow.set_tag("purpose", "research-only")
            revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
            mlflow.set_tag("source_revision", revision.stdout.strip())
            mlflow.set_tag("working_tree", "uncommitted research code")
            print(f"MLflow experiment: {mlflow.active_run().info.experiment_id}; run: {mlflow.active_run().info.run_id}")
    print(pd.DataFrame(results).groupby("method")[["mae", "rmse", "wape", "bias"]].mean().round(3))
    print(f"Fold results: {len(results)}; exclusions: {len(exclusions)}; output: {output}")


if __name__ == "__main__":
    main()
