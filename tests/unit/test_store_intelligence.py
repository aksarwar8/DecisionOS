from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas.store_intelligence import MatrixQuery, StoreRankingQuery
from backend.main import app
from backend.services import store_intelligence_service as service
from backend.services.sales_intelligence_service import SalesQueryTimeout

WINDOW = {
    "period_start": date(2016, 3, 26), "period_end": date(2016, 4, 24),
    "latest_sales_date": date(2016, 4, 24), "period_days": 30,
}
STORE = {
    "group_id": 1, "label": "CA_1", "store_id": 1, "state": "CA", "store_code": "CA_1",
    "total_demand": 6, "previous_demand": 0, "absolute_change": 6, "percentage_growth": None,
    "average_daily_demand": 0.2, "observed_days": 2, "previous_observed_days": 1,
    "positive_demand_days": 1, "observed_products": 3, "positive_demand_products": 1,
    "contribution_pct": 60,
}
MATRIX = {
    "geography_id": 1, "geography_label": "CA_1", "merchandise_id": "FOODS",
    "merchandise_label": "FOODS", "total_demand": None, "previous_demand": 2,
    "contribution_pct": None, "percentage_growth": None,
}


@pytest.mark.parametrize(("sort", "expression"), [
    ("top", "total_demand DESC"), ("bottom", "total_demand ASC"), ("growth", "percentage_growth DESC"),
    ("decline", "percentage_growth ASC"), ("average", "average_daily_demand DESC"),
])
def test_ranking_binds_filters_and_uses_stable_ties(sort, expression):
    query = StoreRankingQuery(state="CA", department="value' --", sort=sort, limit=3)
    statement, params = service.build_entity_statement(query, "store", ranking=True)
    sql = str(statement)
    assert f"ORDER BY {expression}, group_id" in sql
    assert "total_demand IS NOT NULL" in sql
    assert "NULLIF(p.previous_demand, 0)" in sql
    assert "st.state = :state" in sql and "p.department = :department" in sql
    assert params["department"] not in sql
    assert params["state"] == "CA" and params["limit"] == 3
    assert "category' AND" not in sql


@pytest.mark.parametrize(("dimension", "geography", "merchandise"), [
    ("store_category", "store_id", "category"),
    ("store_department", "store_id", "department"),
    ("state_category", "state", "category"),
])
def test_matrix_has_one_anchor_and_preserves_nulls(dimension, geography, merchandise):
    statement, _ = service.build_matrix_statement(MatrixQuery(dimensions=dimension, days=60))
    sql = str(statement)
    assert f"{geography} AS geography_id, {merchandise} AS merchandise_id" in sql
    assert sql.count("latest AS MATERIALIZED") == 1
    assert "LEFT JOIN totals t" in sql
    assert "NULLIF(g.units, 0)" in sql and "NULLIF(t.previous_demand, 0)" in sql


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("path", [
    "store-performance?store_id=0", "store-performance?store_id=1&aggregation=yearly",
    "store-rankings?sort=anything", "store-rankings?limit=51",
    "store-comparison", "store-comparison?store_ids=1&store_ids=1",
    "store-comparison?" + "&".join(f"store_ids={i}" for i in range(1, 7)),
    "category-performance?group_by=product", "demand-matrix?dimensions=category_department",
    "state-performance?days=366",
])
def test_invalid_request_never_reads_database(client, monkeypatch, path):
    read = Mock()
    monkeypatch.setattr(service, "read_sales_statement", read)
    assert client.get(f"/analytics/{path}").status_code == 422
    read.assert_not_called()


def test_store_comparison_response_and_shared_dates(client, monkeypatch):
    second = {**STORE, "group_id": 2, "store_id": 2, "label": "CA_2", "store_code": "CA_2",
              "total_demand": None, "observed_days": 0}
    read = Mock(return_value=({"entities": [STORE, second], "composition": [], "trend": [
        {"group_id": 2, "label": "CA_2", "period": "2016-03-26", "total_demand": None,
         "observed_days": 0, "expected_days": 1},
    ]}, WINDOW))
    monkeypatch.setattr(service, "read_sales_statement", read)
    response = client.get("/analytics/store-comparison?store_ids=1&store_ids=2&state=CA&aggregation=daily")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["previous_period_start"] == "2016-02-25"
    assert result["previous_period_end"] == "2016-03-25"
    assert result["aggregation"] == "daily"
    assert result["entities"][0]["percentage_growth"] is None
    assert result["entities"][0]["previous_demand"] == 0
    assert result["trend"][0]["total_demand"] is None
    assert read.call_args.args[1]["store_ids"] == [1, 2]
    assert read.call_args.args[1]["state"] == "CA"


def test_matrix_returns_null_for_missing_and_safe_timeout(client, monkeypatch):
    read = Mock(return_value=({"cells": [MATRIX]}, WINDOW))
    monkeypatch.setattr(service, "read_sales_statement", read)
    response = client.get("/analytics/demand-matrix?dimensions=store_category")
    assert response.status_code == 200
    assert response.json()["cells"] == [MATRIX]
    read.side_effect = SalesQueryTimeout("private")
    response = client.get("/analytics/demand-matrix")
    assert response.status_code == 503 and response.headers["X-Request-ID"]
    assert "private" not in response.text


def test_dashboard_requests_only_current_view_and_clears_stale_results(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from dashboard import api_client
    from dashboard.catalog_widgets import _catalog_data

    def block_network(*args, **kwargs):
        raise AssertionError("Dashboard tests must not use live services.")

    monkeypatch.setattr("requests.sessions.Session.request", block_network)
    for name, payload in {
        "get_catalog_states": {"states": ["CA"]},
        "get_catalog_stores": [{"store_id": 1, "store_code": "CA_1"}, {"store_id": 2, "store_code": "CA_2"}],
        "get_catalog_categories": {"categories": ["FOODS"]},
        "get_catalog_departments": {"departments": ["FOODS_1"]},
    }.items():
        monkeypatch.setattr(api_client, name, Mock(return_value=payload))

    period = {**WINDOW, "previous_period_start": "2016-02-25", "previous_period_end": "2016-03-25"}
    ranking = Mock(return_value={**period, "entities": [STORE], "trend": [], "composition": []})
    matrix = Mock(return_value={**period, "cells": [
        {**MATRIX, "total_demand": 10, "contribution_pct": 100, "percentage_growth": 400},
        {**MATRIX, "merchandise_id": "HOBBIES", "merchandise_label": "HOBBIES"},
    ]})
    comparison = Mock(return_value={**ranking.return_value, "entities": [
        STORE, {**STORE, "group_id": 2, "label": "CA_2", "store_id": 2, "store_code": "CA_2"},
    ]})
    monkeypatch.setattr(api_client, "get_store_rankings", ranking)
    monkeypatch.setattr(api_client, "get_demand_matrix", matrix)
    monkeypatch.setattr(api_client, "get_store_comparison", comparison)
    _catalog_data.clear()
    try:
        at = AppTest.from_file(
            Path(__file__).resolve().parents[2] / "dashboard" / "app.py", default_timeout=20,
        ).run()
        at.sidebar.radio[0].set_value("Store & Category Intelligence").run()
        ranking.assert_not_called()
        at.button[0].click().run()
        assert not at.exception and at.dataframe and ranking.call_count == 1
        at.selectbox(key="sci_days").set_value(60).run()
        assert not at.dataframe and ranking.call_count == 1
        at.selectbox(key="sci_mode").set_value("Compare stores").run()
        assert at.multiselect(key="sci_store_basket").options == ["CA_1", "CA_2"]
        at.multiselect(key="sci_store_basket").set_value([1, 2]).run()
        comparison.assert_not_called()
        at.button[0].click().run()
        assert comparison.call_args.kwargs["store_ids"] == (1, 2)
        assert at.get("plotly_chart")
        at.selectbox(key="sci_compare_metric").set_value("Demand growth (%)").run()
        assert not at.exception and comparison.call_count == 1
        at.selectbox(key="sci_mode").set_value("Demand matrix").run()
        matrix.assert_not_called()
        assert not at.dataframe
        at.button[0].click().run()
        assert not at.exception and at.get("plotly_chart") and at.get("download_button")
        at.selectbox(key="sci_matrix_metric").set_value("Demand growth (%)").run()
        assert not at.exception and matrix.call_count == 1
    finally:
        _catalog_data.clear()
