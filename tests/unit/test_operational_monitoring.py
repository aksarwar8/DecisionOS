import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from src.decisionos.monitoring.drift import distribution_drift


def test_drift_constant_missing_and_shift():
    same = distribution_drift([0] * 20 + [np.nan], [0] * 20)
    assert same["reference_missing"] == 1
    assert same["psi"] == 0
    shifted = distribution_drift([0] * 20, [1] * 20)
    assert shifted["ks"] == 1
    assert shifted["psi"] > 0


def test_drift_reports_insufficient_data():
    result = distribution_drift([1, 2], [1, 2])
    assert result["status"] == "insufficient_data"
    assert result["psi"] is None


def test_metrics_and_safe_readiness_failure(monkeypatch):
    def unavailable():
        raise RuntimeError("secret database details")

    monkeypatch.setattr("backend.api.routes.health.get_engine", unavailable)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "secret" not in response.text
        assert response.headers["X-Request-ID"]
        metrics = client.get("/metrics").json()
        assert metrics["requests"] >= 1
        assert metrics["server_errors"] >= 1
