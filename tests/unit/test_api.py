from unittest.mock import Mock
from uuid import UUID

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.routes import analytics, forecast, model, prediction
from backend.main import app
from backend.services.analytics_service import AnalyticsNotFoundError
from src.decisionos.config import Settings
from src.decisionos.data.validate import HistoricalSalesError

FORECAST_REQUEST = {"product_id": 1, "store_id": 2, "horizon": 7}
PREDICTION_REQUEST = {
    "product_id": 1, "store_id": 2,
    "year": 2021, "month": 1, "day": 1, "day_of_week": 4,
    "week_of_year": 53, "is_weekend": 0,
    "lag_7": 1, "lag_14": 1, "lag_28": 1,
    "rolling_mean_7": 1, "rolling_mean_28": 1, "rolling_std_7": 0,
}


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_health_returns_distinct_request_ids(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "application": "DecisionOS"}
    request_id = UUID(response.headers["X-Request-ID"])
    assert UUID(client.get("/health").headers["X-Request-ID"]) != request_id


def test_forecast_request_validation_precedes_service(client, monkeypatch):
    service = Mock()
    monkeypatch.setattr(forecast, "generate_product_forecast", service)
    invalid = {**FORECAST_REQUEST, "horizon": 8}
    response = client.post("/forecast/", json=invalid)
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
    service.assert_not_called()


def test_forecast_response_contract(client, monkeypatch):
    dates = pd.date_range("2021-01-29", periods=7)
    service = Mock(return_value=pd.DataFrame({
        "date": dates, "demand_segment": "Low demand",
        "selected_model": "Random Forest", "prediction": 1.5,
    }))
    monkeypatch.setattr(forecast, "generate_product_forecast", service)
    response = client.post("/forecast/", json=FORECAST_REQUEST)
    assert response.status_code == 200
    service.assert_called_once_with(**FORECAST_REQUEST)
    body = response.json()
    assert body["total_predicted_demand"] == 10.5
    assert [day["date"] for day in body["forecasts"]] == dates.strftime("%Y-%m-%d").tolist()
    assert body["forecasts"][0]["selected_model"] == "Random Forest"


def test_expected_history_error_preserves_message(client, monkeypatch):
    service = Mock(side_effect=HistoricalSalesError("Historical sales contain missing dates."))
    monkeypatch.setattr(forecast, "generate_product_forecast", service)
    response = client.post("/forecast/", json=FORECAST_REQUEST)
    assert response.status_code == 400
    assert response.json()["detail"] == "Historical sales contain missing dates."


@pytest.mark.parametrize("url", ["/analytics/overview?days=0", "/analytics/stores/0"])
def test_analytics_query_and_path_validation(client, monkeypatch, url):
    service = Mock()
    monkeypatch.setattr(analytics, "get_platform_overview", service)
    monkeypatch.setattr(analytics, "get_store_summary", service)
    assert client.get(url).status_code == 422
    service.assert_not_called()


def test_analytics_missing_resource(client, monkeypatch):
    service = Mock(side_effect=AnalyticsNotFoundError("Product 99 not found."))
    monkeypatch.setattr(analytics, "get_product_summary", service)
    response = client.get("/analytics/products/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product 99 not found."


def test_analytics_trend_keeps_pair_anchor_and_calendar_day_denominator(client, monkeypatch):
    trend = pd.DataFrame({
        "date": pd.to_datetime(["2021-01-01", "2021-01-03"]),
        "sales_quantity": [0, 12],
    })
    monkeypatch.setattr(analytics, "get_product_store_trend", Mock(return_value=trend))
    response = client.get("/analytics/trends?product_id=1&store_id=2&days=4")
    assert response.status_code == 200
    body = response.json()
    assert (body["period_start"], body["period_end"]) == ("2020-12-31", "2021-01-03")
    assert (body["positive_sales_days"], body["observed_days"]) == (1, 2)
    assert (body["average_daily_demand"], body["average_observed_day_demand"]) == (3, 6)


def test_model_info_uses_configured_registry_identity(client, monkeypatch):
    registry = Mock()
    registry.get_model_version_by_alias.return_value = Mock(
        name="registry-version", version="3", status="READY",
    )
    registry.get_model_version_by_alias.return_value.name = "Example"
    monkeypatch.setattr(model, "get_mlflow_client", lambda: registry)
    monkeypatch.setattr(model, "get_settings", lambda: Settings(
        model_name="Example", model_alias="test-alias",
    ))
    response = client.get("/model/info")
    assert response.status_code == 200
    assert response.json()["model_uri"] == "models:/Example@test-alias"
    registry.get_model_version_by_alias.assert_called_once_with(
        name="Example", alias="test-alias",
    )


@pytest.mark.parametrize(("route", "module", "service", "payload"), [
    ("/forecast/", forecast, "generate_product_forecast", FORECAST_REQUEST),
    ("/predict/", prediction, "load_forecasting_model", PREDICTION_REQUEST),
])
def test_unexpected_errors_are_logged_and_return_safe_response(
    client, monkeypatch, caplog, route, module, service, payload,
):
    monkeypatch.setattr(module, service, Mock(side_effect=ValueError("internal-only detail")))
    response = client.post(route, json=payload)
    assert response.status_code == 500
    request_id = response.headers["X-Request-ID"]
    assert response.json() == {"detail": "An internal error occurred.", "request_id": request_id}
    assert "internal-only detail" in caplog.text
    assert request_id in caplog.text
