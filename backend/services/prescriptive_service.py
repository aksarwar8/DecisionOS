"""Simulated decisions using previously saved single-pair forecast runs."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from backend.api.schemas.prescriptive import Assumptions, DecisionRequest, DecisionResponse
from backend.services.forecast_runs import get_run
from backend.services import operational_store
from src.decisionos.config import Settings
from src.decisionos.inventory.decisions import allocate, recommend


def synthetic_assumptions(product_id, store_id, seed):
    digest = hashlib.sha256(f"{seed}:{product_id}:{store_id}".encode()).digest()
    return Assumptions(stock=10 + digest[0] % 50, incoming=digest[1] % 10,
                       lead_days=3 + digest[2] % 8, safety_stock=5 + digest[3] % 20,
                       unit_cost=round(1 + digest[4] / 50, 2))


def make_decision(request: DecisionRequest, demand_multiplier=1, order_override=None):
    run = get_run(request.run_id)
    result = run.get("result")
    if run["status"] != "completed" or not result or result["coverage"] != "complete":
        raise ValueError("A completed forecast with complete coverage is required.")
    scope = result["scope"]
    if result["candidate_pairs"] != 1 or result["eligible_pairs"] != 1:
        raise ValueError("Inventory decisions require a complete single-pair forecast run.")
    if scope["scope"] == "pair":
        product, store = scope["product_ids"][0], scope["store_ids"][0]
    elif scope["scope"] == "pairs" and len(scope["pairs"]) == 1:
        product, store = scope["pairs"][0]["product_id"], scope["pairs"][0]["store_id"]
    else:
        raise ValueError("Select an explicit single-pair forecast run.")
    daily = result["daily"]
    origin = pd.Timestamp(result["origin"])
    expected = pd.date_range(origin + pd.Timedelta(days=1), periods=len(daily))
    dates = pd.to_datetime([item["date"] for item in daily])
    if not dates.equals(expected) or len(daily) != scope["horizon"]:
        raise ValueError("Forecast dates do not align with the forecast origin and horizon.")
    values = [float(item["prediction"]) * demand_multiplier for item in daily]
    if not all(pd.notna(value) and 0 <= value < float("inf") for value in values):
        raise ValueError("Forecast values must be finite and nonnegative.")
    metrics = recommend(values, request.assumptions.model_dump(), order_override=order_override)
    for day, date in zip(metrics["projection"], dates):
        day["date"] = date.date()
    return DecisionResponse(
        product_id=product, store_id=store, run_id=request.run_id, forecast_origin=origin.date(),
        model_uri=result["model_uri"], model_version=result["model_version"], method=scope.get("method", "hybrid"),
        assumptions=request.assumptions, **metrics,
        explanation=(f"Inventory position {metrics['inventory_position']:.2f}; "
                     f"lead-time demand {metrics['lead_time_demand']:.2f}; "
                     f"reorder point {metrics['reorder_point']:.2f}; "
                     f"recommended order {metrics['recommended_quantity']} units."),
        limitation=("All inventory and cost inputs are simulated. Incoming and new orders arrive after the "
                    "lead time. Service level is an assumption and does not calculate safety stock. "
                    "Point forecasts are not stockout probabilities."),
    )


def budget_allocation(items, budget):
    decisions = [make_decision(item) for item in items]
    if len({(item.product_id, item.store_id) for item in decisions}) != len(decisions):
        raise ValueError("Each product-store pair must appear only once.")
    candidates = []
    for request, item in zip(items, decisions):
        unit = item.assumptions.unit_cost
        no_order = make_decision(request, order_override=0)
        benefit = ((no_order.projected_shortage - item.projected_shortage) * item.assumptions.shortage_cost
                   - (item.holding_exposure - no_order.holding_exposure))
        quantity = item.recommended_quantity if benefit > 0 else 0
        candidates.append({"product_id": item.product_id, "store_id": item.store_id,
                           "quantity": quantity,
                           "unit_cost": unit, "minimum_order": item.assumptions.minimum_order,
                           "order_multiple": item.assumptions.order_multiple,
                           "priority_score": (benefit / (unit * quantity) if unit else 1e300)
                           if quantity else 0})
    return allocate(candidates, budget)


def save_review(review):
    if operational_store.enabled():
        identifier = str(uuid4())
        record = {"id": identifier, "created_at": datetime.now(timezone.utc).isoformat(),
                  **review.model_dump(mode="json")}
        operational_store.put("review", identifier, record, insert_only=True)
        return record
    directory = Settings.project_path("decision_reviews")
    directory.mkdir(parents=True, exist_ok=True)
    identifier = str(uuid4())
    record = {"id": identifier, "created_at": datetime.now(timezone.utc).isoformat(),
              **review.model_dump(mode="json")}
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
        temp = Path(handle.name)
        try:
            json.dump(record, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, directory / (identifier + ".json"))
    finally:
        temp.unlink(missing_ok=True)
    return record


def list_reviews():
    if operational_store.enabled():
        return operational_store.recent("review", 100)
    directory = Settings.project_path("decision_reviews")
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(
        directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:100]]         if directory.is_dir() else []


def save_inventory(product_id, store_id, assumptions):
    if operational_store.enabled():
        record = {"product_id": product_id, "store_id": store_id,
                  "assumptions": assumptions.model_dump(mode="json"), "label": "simulated"}
        operational_store.put("inventory", f"{product_id}:{store_id}", record)
        return record
    directory = Settings.project_path("simulated_inventory")
    directory.mkdir(parents=True, exist_ok=True)
    record = {"product_id": product_id, "store_id": store_id,
              "assumptions": assumptions.model_dump(mode="json"), "label": "simulated"}
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(record, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, directory / f"{product_id}_{store_id}.json")
    finally:
        temporary.unlink(missing_ok=True)
    return record


def load_inventory(product_id, store_id):
    if operational_store.enabled():
        try:
            return operational_store.get("inventory", f"{product_id}:{store_id}")
        except FileNotFoundError:
            pass
    path = Settings.project_path("simulated_inventory") / f"{product_id}_{store_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))
