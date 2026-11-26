from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas.sales_intelligence import SalesFilters, SalesReportResponse
from backend.main import app
from backend.services import sales_intelligence_service as service
from backend.services.analytics_service import AnalyticsNotFoundError

WINDOW = {
    "period_start": date(2021, 1, 3), "period_end": date(2021, 1, 4),
    "latest_sales_date": date(2021, 1, 5), "period_days": 2,
}


def _day(day, demand):
    return {"dimension": "day", "sale_day": day, "total_demand": demand}


def test_equal_adjacent_windows_and_growth_despite_partial_observations():
    growth = service.summarize_growth(WINDOW, [
        _day("2021-01-01", 10), _day("2021-01-03", 15), _day("2021-01-04", 5),
    ])
    assert growth["previous"] == {
        "start": date(2021, 1, 1), "end": date(2021, 1, 2), "total_demand": 10,
        "observed_days": 1, "missing_days": 1,
    }
    assert growth["current"]["start"] == date(2021, 1, 3)
    assert growth["current"]["end"] == date(2021, 1, 4)
    assert growth["current"]["total_demand"] == 20
    assert growth["current"]["observed_days"] == 2
    assert growth["absolute_change"] == 10
    assert growth["percentage_change"] == 100


def test_observed_zero_baseline_and_missing_baseline_are_distinct():
    current = _day("2021-01-04", 10)
    zero = service.summarize_growth(WINDOW, [current, _day("2021-01-02", 0)])
    missing = service.summarize_growth(WINDOW, [current])
    assert zero["previous"]["total_demand"] == 0
    assert zero["previous"]["observed_days"] == 1
    assert zero["absolute_change"] == 10
    assert zero["percentage_change"] is None
    assert missing["previous"]["total_demand"] is None
    assert missing["previous"]["missing_days"] == 2
    assert missing["absolute_change"] is None
    assert missing["percentage_change"] is None


def test_unknown_breakdown_group_counts_toward_share_denominator():
    groups = [
        {"dimension": "category", "category": "A", "current_observations": 2, "current_demand": 7},
        {"dimension": "category", "category": None, "current_observations": 1, "current_demand": 3},
        {"dimension": "category", "category": "Previous only", "current_observations": 0},
    ]
    rows = service.summarize_breakdown(groups, "category")
    assert [row["percentage_contribution"] for row in rows] == [70, 30]
    assert rows[1]["group_id"] is None
    assert rows[1]["label"] == "Unknown category"
    assert rows[1]["observation_count"] == 1
    groups[0]["current_demand"] = groups[1]["current_demand"] = 0
    assert all(row["percentage_contribution"] is None for row in service.summarize_breakdown(
        groups, "category",
    ))


@pytest.mark.parametrize(("entity", "key"), [("product", "product_id"), ("store", "store_id")])
def test_rankings_include_observed_zero_and_break_ties_by_id(entity, key):
    rows = [
        {"dimension": entity, key: i, f"{entity}_code": str(i),
         "current_demand": demand, "current_observations": observations}
        for i, demand, observations in [(5, 20, 1), (1, 20, 2), (2, 0, 1), (3, None, 0)]
    ]
    top = service.rank_groups(rows, entity, "top", 2)
    bottom = service.rank_groups(rows, entity, "bottom", 3)
    assert [(row["rank"], row["entity_id"]) for row in top] == [(1, 1), (2, 5)]
    assert [row["entity_id"] for row in bottom] == [2, 1, 5]


@pytest.mark.parametrize(("aggregation", "bucket"), [
    ("daily", "sale_day"), ("weekly", "date_trunc('week', sale_day)::date"),
    ("monthly", "date_trunc('month', sale_day)::date"),
])
def test_aggregation_sql_has_one_materialized_anchor_and_bound_filters(aggregation, bucket):
    filters = SalesFilters(
        days=30, end_date=date(2021, 1, 4), state="XX' --", store_id=10,
        category="category text", department="department text", product_id=42,
    )
    query, params = service.build_sales_query(
        filters, ("day", "state"), comparison=True, aggregation=aggregation,
    )
    sql = str(query)
    assert f"SELECT {bucket} AS period" in sql
    assert "ORDER BY t.period" in sql
    assert "period_start - :days" in sql
    assert sql.count("latest AS MATERIALIZED") == 1
    for key in ("store_id", "product_id", "category", "department", "state"):
        assert params[key] == getattr(filters, key)
        assert f"= :{key}" in sql
    assert "XX' --" not in sql
    assert params["end_date"] == date(2021, 1, 4)


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def database(monkeypatch):
    engine = MagicMock()
    monkeypatch.setattr(service, "get_engine", engine)
    return engine().connect().__enter__()


def test_report_empty_window_returns_typed_empty_sections(client, database):
    database.execute.return_value.mappings.return_value.one.return_value = {
        **WINDOW, "groups": [], "trend": [],
    }
    response = client.get("/analytics/sales-report?days=2&view=executive&aggregation=monthly")
    assert response.status_code == 200, response.text
    report = SalesReportResponse.model_validate(response.json())
    assert report.aggregation == "monthly"
    assert report.growth.current.total_demand is None
    assert report.growth.current.missing_days == 2
    assert report.average_daily_demand is None
    assert report.active_products == report.active_stores == 0
    assert report.breakdowns == {"category": []}
    assert report.trend == report.top_stores == report.top_products == []
    assert response.headers["X-Request-ID"]
    database.exec_driver_sql.assert_called_once_with("SET LOCAL statement_timeout = '25s'")
    database.execute.assert_called_once()


@pytest.mark.parametrize("url", [
    "/analytics/growth?days=366", "/analytics/growth?end_date=yesterday",
    "/analytics/growth?store_id=0", "/analytics/growth?category=",
    "/analytics/sales-trend?aggregation=yearly", "/analytics/breakdown?group_by=price",
    "/analytics/rankings?entity=category", "/analytics/rankings?order=random",
    "/analytics/rankings?limit=51", "/analytics/sales-report?view=unknown",
])
def test_invalid_inputs_do_not_query_database(client, database, url):
    assert client.get(url).status_code == 422
    database.execute.assert_not_called()


def test_future_end_date_rejected_without_silently_clamping(client, database):
    database.execute.return_value.mappings.return_value.one.return_value = {
        **WINDOW, "period_end": date(2021, 1, 6),
    }
    response = client.get("/analytics/growth?days=2&end_date=2021-01-06")
    assert response.status_code == 422
    assert response.json()["detail"] == "End date must be on or before the latest actual sales date."


@pytest.mark.parametrize(("error", "status"), [
    (AnalyticsNotFoundError("No platform sales data found."), 404),
    (service.SalesQueryTimeout("internal planner details"), 503),
    (RuntimeError("internal planner details"), 500),
])
def test_expected_and_unexpected_errors_are_safe(client, monkeypatch, error, status):
    def fail(_filters):
        raise error

    monkeypatch.setattr(service, "get_growth", fail)
    response = client.get("/analytics/growth")
    assert response.status_code == status
    assert response.headers["X-Request-ID"]
    assert "internal planner details" not in response.text


def test_dashboard_loads_only_on_click_and_clears_results_on_filter_changes(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from dashboard import api_client
    from dashboard.catalog_widgets import _catalog_data

    def block_network(*args, **kwargs):
        raise AssertionError("Dashboard tests must not call live services.")

    monkeypatch.setattr("requests.sessions.Session.request", block_network)
    monkeypatch.setattr(api_client, "get_catalog_categories", lambda: {"categories": ["FOODS"]})
    monkeypatch.setattr(
        api_client, "get_catalog_departments", lambda **kwargs: {"departments": ["FOODS_1"]},
    )
    monkeypatch.setattr(api_client, "get_catalog_states", lambda: {"states": ["CA", "TX"]})
    monkeypatch.setattr(api_client, "get_catalog_stores", lambda state: [
        {"store_id": i, "store_code": f"{region}_1"}
        for i, region in [(1, "CA"), (5, "TX")] if state is None or state == region
    ])
    entry = {
        "group_id": "FOODS", "label": "FOODS", "total_demand": 63,
        "percentage_contribution": 100, "observation_count": 29,
    }
    rank = {"rank": 1, "entity_id": 4, "code": "HOBBIES_1_004", "total_demand": 63}
    report = MagicMock(return_value={
        "period_end": "2016-04-24", "period_days": 30, "aggregation": "weekly",
        "growth": {
            "current": {"start": "2016-03-26", "end": "2016-04-24", "total_demand": 63,
                        "observed_days": 29, "missing_days": 1},
            "previous": {"start": "2016-02-25", "end": "2016-03-25", "total_demand": 52,
                         "observed_days": 30, "missing_days": 0},
            "absolute_change": 11, "percentage_change": 21.15,
        },
        "average_daily_demand": 2.1, "active_products": 1, "active_stores": 1,
        "trend": [{"period": "2016-04-18", "total_demand": 63, "observed_days": 7}],
        "breakdowns": {group: [entry] for group in ("category", "department", "store", "state")},
        "top_products": [rank], "top_stores": [{**rank, "code": "CA_1"}],
    })
    monkeypatch.setattr(api_client, "get_sales_report", report)
    _catalog_data.clear()
    try:
        dashboard_path = Path(__file__).resolve().parents[2] / "dashboard" / "app.py"
        dashboard = AppTest.from_file(dashboard_path, default_timeout=20).run()
        report.assert_not_called()
        dashboard.button(key="executive_load_report").click().run()
        report.assert_called_once_with(view="executive", days=30, aggregation="weekly", end_date=None)
        assert not dashboard.exception and len(dashboard.dataframe) == 2 and dashboard.warning
        dashboard.selectbox(key="executive_days").set_value(60).run()
        assert not dashboard.metric and report.call_count == 1

        dashboard.radio[0].set_value("Sales Intelligence").run()
        for key, value in [
            ("sales_state", "CA"), ("sales_store", 1),
            ("sales_category", "FOODS"), ("sales_department", "FOODS_1"),
        ]:
            dashboard.selectbox(key=key).set_value(value).run()
        assert report.call_count == 1
        dashboard.button(key="sales_load_report").click().run()
        assert not dashboard.exception and len(dashboard.get("plotly_chart")) == 4
        assert dashboard.get("download_button")
        assert report.call_args.kwargs == {
            "view": "sales", "days": 30, "aggregation": "weekly", "end_date": None,
            "state": "CA", "store_id": 1, "category": "FOODS", "department": "FOODS_1",
        }
        dashboard.radio(key="sales_geography").set_value("State").run()
        assert dashboard.metric and report.call_count == 2
        dashboard.selectbox(key="sales_state").set_value("TX").run()
        assert not dashboard.exception and not dashboard.metric
        assert dashboard.selectbox(key="sales_store").value is None
        assert report.call_count == 2
    finally:
        _catalog_data.clear()
