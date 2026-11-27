import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.schemas.prescriptive import Assumptions, DecisionRequest
from backend.main import app
from backend.services import prescriptive_service
from src.decisionos.inventory.decisions import allocate, order_quantity, recommend
from src.decisionos.inventory.simulation import simulate


def test_reorder_constraints_and_arrival_timing():
    assumptions = Assumptions(stock=3, incoming=0, lead_days=2, safety_stock=2,
                              minimum_order=5, order_multiple=4)
    result = recommend([2]*28, assumptions.model_dump())
    assert result["inventory_position"] == 3 and result["reorder_point"] == 6
    assert result["recommended_quantity"] == 20
    assert result["projection"][0]["unfulfilled"] == 0
    assert result["projection"][1]["unfulfilled"] == 1
    assert result["projection"][2]["stock"] == 18
    assert order_quantity(0, 5, 4) == 0


def test_budget_and_zero_demand():
    result = recommend([0]*28, Assumptions(stock=0, safety_stock=0).model_dump())
    assert result["recommended_quantity"] == 0 and result["coverage_days"] is None
    items = [{"product_id": 1, "store_id": 1, "priority_score": 2, "quantity": 12,
              "order_multiple": 4, "minimum_order": 4, "unit_cost": 3},
             {"product_id": 2, "store_id": 1, "priority_score": 1, "quantity": 10,
              "order_multiple": 5, "minimum_order": 5, "unit_cost": 2}]
    value = allocate(items, 40)
    assert value["spent"] <= 40 and value["allocations"][0]["quantity"] == 12
    assert value["allocations"][1]["quantity"] == 0


def test_policy_simulation_is_chronological_and_stockout_correct():
    dates = pd.date_range("2021-01-01", periods=60)
    df = pd.DataFrame({"product_id": 1, "store_id": 1, "date": dates, "sales_quantity": np.ones(60)})
    assumptions = Assumptions(stock=0, incoming=0).model_dump()
    baseline = simulate(df, assumptions, "none")
    assert baseline["stockout_days"] == 32 and baseline["fill_rate"] == 0
    forecast = simulate(df, assumptions, "forecast")
    changed = df.copy()
    changed.loc[50:, "sales_quantity"] = 30
    altered = simulate(changed, assumptions, "forecast")
    assert forecast["trace"][:22] == altered["trace"][:22]
    assert forecast["total_relevant_cost"] >= 0


def test_reject_misaligned_forecast(monkeypatch):
    from uuid import uuid4
    identifier = uuid4()
    run = {"status": "completed", "result": {"coverage": "complete", "candidate_pairs": 1, "eligible_pairs": 1,
           "scope": {"scope": "pair", "product_ids": [1], "store_ids": [2], "horizon": 28},
           "origin": "2020-01-01", "daily": [{"date": "2020-01-03", "prediction": 2}]*28}}
    monkeypatch.setattr(prescriptive_service, "get_run", lambda _: run)
    with pytest.raises(ValueError, match="align"):
        prescriptive_service.make_decision(DecisionRequest(run_id=identifier))


def test_api_validation_and_reproducible_assumptions():
    client = TestClient(app)
    a = client.get("/prescriptive/assumptions", params={"product_id": 1, "store_id": 2, "seed": 42})
    b = client.get("/prescriptive/assumptions", params={"product_id": 1, "store_id": 2, "seed": 42})
    assert a.status_code == 200 and a.json() == b.json()
    assert client.post("/prescriptive/allocation", json={"items": [], "budget": -1}).status_code == 422

def test_scenario_budget_recomputes_projected_shortage(monkeypatch):
    from uuid import uuid4
    identifier = uuid4()
    dates = pd.date_range("2020-01-02", periods=28)
    run = {"status": "completed", "result": {"coverage": "complete", "candidate_pairs": 1, "eligible_pairs": 1,
           "scope": {"scope": "pair", "product_ids": [1], "store_ids": [2], "horizon": 28, "method": "tsb"},
           "origin": "2020-01-01", "model_uri": "builtin:tsb", "model_version": "v1",
           "daily": [{"date": date.date().isoformat(), "prediction": 2} for date in dates]}}
    monkeypatch.setattr(prescriptive_service, "get_run", lambda _: run)
    client = TestClient(app)
    body = {"run_id": str(identifier), "assumptions": {"stock": 3, "incoming": 0, "lead_days": 2,
             "safety_stock": 2, "minimum_order": 4, "order_multiple": 4, "unit_cost": 2}, "budget": 8}
    response = client.post("/prescriptive/scenario", json=body)
    assert response.status_code == 200
    value = response.json()
    assert value["budget_allocation"]["spent"] == 8
    assert value["scenario"]["recommended_quantity"] == 4
    assert value["scenario"]["projected_shortage"] > value["baseline"]["projected_shortage"]

def test_simulated_review_persists_and_is_retrievable(tmp_path, monkeypatch):
    from uuid import uuid4
    identifier = uuid4()
    dates = pd.date_range("2020-01-02", periods=28)
    run = {"status": "completed", "result": {"coverage": "complete", "candidate_pairs": 1, "eligible_pairs": 1,
           "scope": {"scope": "pair", "product_ids": [1], "store_ids": [2], "horizon": 28, "method": "tsb"},
           "origin": "2020-01-01", "model_uri": "builtin:tsb", "model_version": "v1",
           "daily": [{"date": date.date().isoformat(), "prediction": 2} for date in dates]}}
    monkeypatch.setattr(prescriptive_service, "get_run", lambda _: run)
    monkeypatch.setattr(prescriptive_service.Settings, "project_path", lambda _: tmp_path)
    decision = prescriptive_service.make_decision(DecisionRequest(run_id=identifier))
    client = TestClient(app)
    response = client.post("/prescriptive/reviews",
                           json={"decision": decision.model_dump(mode="json"), "status": "approved"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert client.get("/prescriptive/reviews").json()[0]["id"] == response.json()["id"]

def test_simulated_inventory_record_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(prescriptive_service.Settings, "project_path", lambda _: tmp_path)
    client = TestClient(app)
    assert client.get("/prescriptive/inventory/3/2").status_code == 404
    response = client.put("/prescriptive/inventory/3/2", json={"stock": 17, "lead_days": 3})
    assert response.status_code == 200 and response.json()["label"] == "simulated"
    assert client.get("/prescriptive/inventory/3/2").json()["assumptions"]["stock"] == 17
    assert client.put("/prescriptive/inventory/3/2", json={"stock": -1}).status_code == 422

def test_budget_policy_never_exceeds_simulated_procurement_budget():
    dates = pd.date_range("2021-01-01", periods=90)
    df = pd.DataFrame({"product_id": 1, "store_id": 1, "date": dates, "sales_quantity": np.full(90, 4)})
    settings = Assumptions(stock=0, incoming=0, unit_cost=3, simulation_budget=25,
                           minimum_order=4, order_multiple=4).model_dump()
    result = simulate(df, settings, "budget")
    assert result["procurement_cost"] <= 25
    assert result["replenishment_quantity"] % 4 == 0
