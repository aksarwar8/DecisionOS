"""Reproduce a bounded historical inventory simulation using existing PostgreSQL."""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from src.decisionos.inventory.simulation import simulate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--product", type=int, default=4)
    parser.add_argument("--store", type=int, default=1)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Choose a new output directory.")
    output.mkdir(parents=True)
    os.environ["DECISIONOS_FORECAST_RUN_DIR"] = str(output.resolve() / "forecasts")
    client = TestClient(app)
    forecast = client.post("/forecast/runs", json={"scope": "pair", "product_ids": [args.product],
                                                   "store_ids": [args.store], "horizon": 28,
                                                   "method": "tsb", "batch_size": 1})
    forecast.raise_for_status()
    run = forecast.json()
    assumptions = {"stock": 12, "incoming": 0, "lead_days": 7, "safety_stock": 8,
                   "minimum_order": 5, "order_multiple": 5, "unit_cost": 2,
                   "holding_cost": 0.02, "shortage_cost": 4}
    body = {"run_id": run["run_id"], "assumptions": assumptions}
    calls = {
        "recommendation": ("/prescriptive/recommendation", body),
        "scenario": ("/prescriptive/scenario", {**body, "demand_multiplier": 1.25, "lead_days_delta": 2}),
        "budget_scenario": ("/prescriptive/scenario", {**body, "demand_multiplier": 1.25,
                                                       "lead_days_delta": 2, "budget": 40}),
        "simulation": ("/prescriptive/simulation", {"product_id": args.product, "store_id": args.store,
                                                      "assumptions": assumptions}),
    }
    results = {"forecast_run": run}
    for name, (url, payload) in calls.items():
        response = client.post(url, json=payload)
        response.raise_for_status()
        results[name] = response.json()
    historical = pd.DataFrame([
        {"product_id": args.product, "store_id": args.store, "date": item["date"],
         "sales_quantity": item["demand"]} for item in run["result"]["historical"]
    ])
    alternative = results["simulation"]["assumptions"] | {"shortage_cost": 1}
    results["alternative_cost"] = {
        "assumptions": alternative,
        "policies": [simulate(historical, alternative, policy)
                     for policy in ("none", "fixed", "reorder", "forecast", "budget")],
    }
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Saved", output / "results.json")


if __name__ == "__main__":
    main()
