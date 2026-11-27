"""Reconstruct training-only diagnostics for a saved cohort and configuration."""

import argparse
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.decisionos.data.extract import get_engine
from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.evaluation.backtest import rolling_windows
from src.decisionos.evaluation.characterize import characterize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    args = parser.parse_args()
    output = Path(args.directory)
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    cohort = pd.read_json(output / "cohort.json")
    folds = list(rolling_windows(config["origins"], config["training_days"], config["horizon"]))
    query = text("""
        SELECT s.product_id, s.store_id, c.date, s.sales_quantity
        FROM unnest(CAST(:products AS integer[]), CAST(:stores AS integer[])) AS p(product_id, store_id)
        JOIN sales s ON s.product_id=p.product_id AND s.store_id=p.store_id
        JOIN calendar c ON c.id=s.calendar_id
        WHERE c.date BETWEEN :start AND :end
        ORDER BY s.product_id,s.store_id,c.date
    """)
    with get_engine().connect() as connection:
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        history = pd.read_sql(query, connection, params={
            "products": cohort.product_id.tolist(), "stores": cohort.store_id.tolist(),
            "start": min(fold[0] for fold in folds).date(), "end": max(fold[1] for fold in folds).date(),
        })
    history.date = pd.to_datetime(history.date)
    rows = []
    for start, origin, _, _ in folds:
        train = history[history.date.between(start, origin)]
        for (product, store), group in train.groupby(["product_id", "store_id"]):
            validate_historical_sales(group)
            if len(group) != config["training_days"]:
                raise ValueError("Training history changed or is incomplete.")
            rows.append({"origin": str(origin.date()), "product_id": product, "store_id": store,
                         **characterize(group.sales_quantity)})
    pd.DataFrame(rows).to_csv(output / "fold_characteristics.csv", index=False)
    print(f"Recorded {len(rows)} training-window characterizations.")


if __name__ == "__main__":
    main()
