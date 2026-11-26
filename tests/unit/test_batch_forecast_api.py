import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.schemas.batch_forecast import BatchRequest
from backend.main import app
from backend.services import batch_forecast_service as service
from src.decisionos.config import Settings


@pytest.fixture
def candidates():
    return pd.DataFrame([
        {"product_id": 1, "store_id": 1, "item_id": "A", "store_code": "CA_1",
         "category": "FOODS", "department": "F1", "state": "CA"},
        {"product_id": 2, "store_id": 1, "item_id": "B", "store_code": "CA_1",
         "category": "FOODS", "department": "F1", "state": "CA"},
    ])


def history(product, dates):
    return pd.DataFrame({"product_id": product, "store_id": 1, "date": dates,
                         "sales_quantity": np.zeros(len(dates)) if product == 2 else np.ones(len(dates))})


@pytest.mark.parametrize("kwargs", [
    {"scope": "pairs", "pairs": [{"product_id": 1, "store_id": 2}] * 2},
    {"scope": "pair", "product_ids": [1, 1], "store_ids": [2]},
    {"scope": "state"}, {"scope": "product", "product_ids": [1, 2]},
])
def test_invalid_scopes_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        BatchRequest(**kwargs)


def test_exclusions_distinguish_missing_and_gapped_history(candidates):
    dates = pd.date_range("2021-01-01", periods=30)
    gaps = history(1, dates.delete(10))
    accepted, excluded = service.partition_histories(candidates, gaps, dates[-1])
    assert accepted.empty and len(excluded) == 2
    assert "missing calendar dates" in excluded[0]["reason"]
    assert "No observations" in excluded[1]["reason"]


def test_preview_rejects_excess_work_before_inference(monkeypatch, candidates):
    monkeypatch.setattr(service, "get_settings", lambda: Settings(forecast_max_pairs="1"))
    preview = service.scope_preview(BatchRequest(scope="business"), candidates)
    assert preview["candidate_pairs"] == 2 and not preview["within_limits"]
    monkeypatch.setattr(service, "resolve_scope", lambda request: candidates)
    with pytest.raises(ValueError, match="exceeds synchronous"):
        service.generate_batch(BatchRequest(scope="business"))


def test_partial_batch_sums_only_eligible_series(monkeypatch, candidates):
    dates = pd.date_range("2021-01-01", periods=30)
    frame = history(1, dates)
    model = type("Model", (), {"predict": lambda self, features: np.full(len(features), 2.0)})()
    monkeypatch.setattr(service, "resolve_scope", lambda request: candidates)
    monkeypatch.setattr(service, "extract_histories", lambda candidates, origin: (frame, dates[-1]))
    monkeypatch.setattr(service, "load_forecasting_model_info", lambda: (model, "7"))
    result = service.generate_batch(BatchRequest(scope="business", horizon=7))
    assert result["coverage"] == "partial" and result["eligible_pairs"] == 1
    assert result["excluded_pairs"] == 1 and result["exclusions"][0]["product_id"] == 2
    assert result["total_prediction"] == pytest.approx(sum(day["prediction"] for day in result["daily"]))
    assert result["model_version"] == "7"
    assert sum(item["prediction"] for item in result["breakdowns"] if item["dimension"] == "store") == 14


def test_api_validation_and_preview(monkeypatch, candidates):
    monkeypatch.setattr(service, "resolve_scope", lambda request: candidates)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/forecast/scope-preview", json={"scope": "business", "horizon": 7}).json()[
            "estimated_rows"
        ] == 14
        assert client.post("/forecast/batch", json={"scope": "pair", "horizon": 3}).status_code == 422


def test_dashboard_preview_and_stale_state(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from dashboard import api_client
    from dashboard.catalog_widgets import _catalog_data

    monkeypatch.setattr(api_client, "get_catalog_categories", lambda: {"categories": ["FOODS"]})
    monkeypatch.setattr(api_client, "get_catalog_departments", lambda **kwargs: {"departments": ["F1"]})
    monkeypatch.setattr(api_client, "get_catalog_states", lambda: {"states": ["CA"]})
    monkeypatch.setattr(api_client, "get_catalog_stores", lambda **kwargs: [
        {"store_id": 1, "store_code": "CA_1"},
    ])
    monkeypatch.setattr(api_client, "get_catalog_products", lambda **kwargs: {
        "products": [{"product_id": 1, "item_id": "A"}], "total": 1,
    })
    calls = []
    monkeypatch.setattr(api_client, "preview_forecast_scope", lambda payload: calls.append(payload.copy()) or {
        "candidate_pairs": 1, "estimated_rows": 7, "max_pairs": 100, "max_rows": 2800,
        "within_limits": True,
    })
    _catalog_data.clear()
    try:
        at = AppTest.from_file(Path(__file__).resolve().parents[2] / "dashboard" / "app.py",
                               default_timeout=20).run()
        at.sidebar.radio[0].set_value("Demand Forecasting").run()
        at.radio[0].set_value("Batch and business scope").run()
        at.selectbox(key="batch_product").set_value(1).run()
        assert not calls
        next(button for button in at.button if button.label == "Preview forecast scope").click().run()
        assert not at.exception and len(calls) == 1
        assert any("candidate pairs" in item.value for item in at.markdown)
        at.selectbox(key="batch_horizon").set_value(14).run()
        assert not at.exception and not any("candidate pairs" in item.value for item in at.markdown)
        assert len(calls) == 1
    finally:
        _catalog_data.clear()
