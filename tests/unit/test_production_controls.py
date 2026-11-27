from dataclasses import replace

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import operational_store
from src.decisionos.config import Settings


def test_mutations_require_configured_token_outside_local(monkeypatch):
    monkeypatch.setattr("backend.main.get_settings", lambda: replace(Settings(), app_env="demo"))
    client = TestClient(app)
    assert client.post("/forecast/scope-preview", json={}).status_code == 503
    monkeypatch.setattr("backend.main.get_settings", lambda: replace(Settings(), app_env="demo", api_admin_token="secret"))
    assert client.post("/forecast/scope-preview", json={}).status_code == 401
    assert client.post("/forecast/scope-preview", json={}, headers={"Authorization": "Bearer secret"}).status_code == 422
    assert client.get("/health").status_code == 200


def test_schema_identifier_rejects_sql_injection(monkeypatch):
    import pytest
    monkeypatch.setenv("DECISIONOS_OPERATIONAL_SCHEMA", "public; DROP TABLE sales")
    with pytest.raises(ValueError):
        operational_store.schema()


def test_experimental_migration_requires_explicit_non_public_schema(monkeypatch):
    import pytest
    monkeypatch.delenv("DECISIONOS_OPERATIONAL_SCHEMA", raising=False)
    with pytest.raises(ValueError):
        operational_store.migration_schema()
    monkeypatch.setenv("DECISIONOS_OPERATIONAL_SCHEMA", "public")
    with pytest.raises(ValueError):
        operational_store.migration_schema()
    monkeypatch.setenv("DECISIONOS_OPERATIONAL_SCHEMA", "decisionos_test")
    assert operational_store.migration_schema() == "decisionos_test"


def test_historical_drift_uses_chronological_halves(monkeypatch):
    values = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=60),
                           "sales_quantity": [0] * 30 + [4] * 30})
    monkeypatch.setattr("backend.api.routes.monitoring.extract_product_store_history",
                        lambda *args, **kwargs: values.iloc[::-1])
    response = TestClient(app).get("/monitoring/demand-drift?product_id=1&store_id=1")
    assert response.status_code == 200
    assert response.json()["alert"] is True
    assert response.json()["diagnostic"]["ks"] == 1
    assert response.json()["mode"] == "historical replay"
