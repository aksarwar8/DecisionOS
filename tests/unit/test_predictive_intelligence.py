import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import forecast_runs
from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.ml.strategies import forecast_history, rolling_intervals
from src.decisionos.monitoring.anomalies import detect_demand_anomalies


def history(values):
    return pd.DataFrame({"product_id": 1, "store_id": 2, "date": pd.date_range("2020-01-01", periods=len(values)),
                         "sales_quantity": values})


def test_strategy_and_interval_bounds():
    data = history([0, 1, 2, 3, 4, 5, 6] * 13)
    result = forecast_history(data, 14, "seasonal_naive")
    assert result.prediction.tolist() == [0, 1, 2, 3, 4, 5, 6] * 2
    bounds, count = rolling_intervals(data, 7, "seasonal_naive", 0.95)
    assert count == 57
    assert all(0 <= item["lower"] <= item["prediction"] <= item["upper"] for item in bounds)
    with pytest.raises(HistoricalSalesError):
        rolling_intervals(history([1]*40), 28, "tsb", 0.95)


def test_anomaly_no_future_leakage_and_zero_handling():
    data = history([2]*30 + [20] + [2]*20)
    first = detect_demand_anomalies(data)
    changed = data.copy()
    changed.loc[40:, "sales_quantity"] = 100
    early = [item for item in detect_demand_anomalies(changed) if item["date"] == data.date.iloc[30].date()]
    assert len(early) == 1 and early[0]["type"] == "spike"
    assert early[0]["evidence"] == first[0]["evidence"]
    assert not detect_demand_anomalies(history([0]*90))
    zero = detect_demand_anomalies(history([2]*30 + [0]*20))
    assert any(item["type"] == "prolonged_zero" for item in zero)


def test_run_storage_round_trip_and_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(forecast_runs, "run_directory", lambda: tmp_path)
    from backend.api.schemas.batch_forecast import BatchRequest
    request = BatchRequest(scope="business")
    def fail(*args, **kwargs):
        raise HistoricalSalesError("test")
    monkeypatch.setattr(forecast_runs, "generate_batch", fail)
    with pytest.raises(HistoricalSalesError):
        forecast_runs.execute_run(request)
    saved = forecast_runs.list_runs()
    assert len(saved) == 1 and saved[0]["status"] == "failed"
    assert "test" not in saved[0]["error"]
    assert forecast_runs.get_run(saved[0]["run_id"])["status"] == "failed"


def test_api_schema_validation_and_methods():
    client = TestClient(app)
    response = client.get("/forecast/methods")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["methods"]} == {
        "hybrid", "tsb", "moving_average", "seasonal_naive"}
    assert client.post("/forecast/intervals", json={"product_id": 1, "store_id": 1,
                                                     "coverage": 0.42}).status_code == 422
    assert client.get("/forecast/runs/not-a-uuid").status_code == 422
    assert client.get("/risk/demand", params={"product_id": 0, "store_id": 1}).status_code == 422

def test_chunked_strategies_and_successful_run(tmp_path, monkeypatch):
    from backend.api.schemas.batch_forecast import BatchRequest
    from backend.services import batch_forecast_service as batch

    days = pd.date_range("2021-01-01", periods=30)
    candidates = pd.DataFrame([{"product_id": i, "store_id": 1, "item_id": str(i),
                                "store_code": "CA_1", "category": "F", "department": "D", "state": "CA"}
                               for i in (1, 2)])
    sales = pd.concat([history([i]*30).assign(product_id=i, store_id=1, date=days) for i in (1, 2)])
    monkeypatch.setattr(batch, "resolve_scope", lambda request: candidates)
    monkeypatch.setattr(batch, "extract_histories", lambda candidates, origin: (sales, days[-1]))
    request = BatchRequest(scope="business", method="moving_average", batch_size=1)
    progress = []
    result = batch.generate_batch(request, progress=lambda done, total: progress.append((done, total)))
    assert progress == [(1, 2), (2, 2)]
    assert result["total_prediction"] == 21
    assert result["model_uri"] == "builtin:moving_average"
    monkeypatch.setattr(forecast_runs, "run_directory", lambda: tmp_path)
    monkeypatch.setattr(forecast_runs, "generate_batch", batch.generate_batch)
    saved = forecast_runs.execute_run(request)
    assert saved["status"] == "completed"
    assert forecast_runs.get_run(saved["run_id"])["result"]["eligible_pairs"] == 2
    assert forecast_runs.list_runs()[0]["completed_pairs"] == 2

def test_store_risk_uses_daily_store_totals(monkeypatch):
    from backend.services import sales_intelligence_service
    dates = pd.date_range("2021-01-01", periods=40)
    trend = [{"period": date.date(), "total_demand": 50 if index == 35 else 5}
             for index, date in enumerate(dates)]
    monkeypatch.setattr(sales_intelligence_service, "get_sales_trend",
                        lambda filters, aggregation: {"trend": trend,
                                                     "period_start": dates[0].date(),
                                                     "period_end": dates[-1].date()})
    client = TestClient(app)
    response = client.get("/risk/store", params={"store_id": 1})
    assert response.status_code == 200
    assert response.json()["anomalies"][0]["type"] == "spike"
    assert response.json()["anomalies"][0]["product_id"] is None
