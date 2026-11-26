import csv
import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas.calendar_intelligence import SeasonalityQuery
from backend.main import app
from backend.services import calendar_intelligence_service as service
from backend.services import price_intelligence_service as prices
from dashboard.business_reports import build_report

WINDOW = {
    "period_start": date(2016, 3, 26), "period_end": date(2016, 4, 24),
    "period_days": 30, "latest_sales_date": date(2016, 4, 24),
}
BUCKET = {
    "label": "Monday", "total_demand": 0, "average_daily_demand": 0, "observed_days": 2,
    "expected_days": 4, "positive_demand_days": 0, "zero_demand_days": 2, "coverage_pct": 50,
    "daily_stddev": 0, "partial_calendar_period": False,
}


def test_event_weekday_baseline_is_reweighted_by_observed_event_mix():
    selected = [
        {"weekday": 1, "observed_days": 3, "total_demand": 12},
        {"weekday": 2, "observed_days": 1, "total_demand": 8},
        {"weekday": 3, "observed_days": 1, "total_demand": 100},
    ]
    baseline = [
        {"weekday": 1, "observed_days": 1, "average_daily_demand": 2},
        {"weekday": 2, "observed_days": 12, "average_daily_demand": 6},
        {"weekday": 3, "observed_days": 0, "average_daily_demand": None},
    ]
    result = service.compare_weekdays(selected, baseline)
    assert result == {
        "matched_observed_days": 4, "comparable_baseline_days": 13, "matched_average_demand": 5,
        "standardized_baseline_average": 3, "absolute_difference": 2,
        "percentage_difference": pytest.approx(200 / 3),
    }


def test_zero_baseline_has_absolute_but_no_percentage_difference():
    assert service.mean_difference(12, 0) == {"absolute_difference": 12, "percentage_difference": None}
    assert service.mean_difference(None, 2) == {"absolute_difference": None, "percentage_difference": None}
    assert service.compare_weekdays([], [])["matched_observed_days"] == 0


def test_capabilities_depend_on_actual_metadata():
    result = service.describe_capabilities({"calendar": {"event_name_1", "snap_ca", "wm_yr_wk"}})
    assert all(not value["available"] for value in result.values())
    result = service.describe_capabilities({
        "calendar": {"wm_yr_wk", "snap_ca", "snap_tx", "snap_wi",
                     "event_name_1", "event_type_1", "event_name_2", "event_type_2"},
        "sell_prices": {"product_id", "store_id", "wm_yr_wk", "sell_price"},
    })
    assert all(value["available"] for value in result.values())


def test_reports_are_deterministic_and_include_loaded_results_and_metadata():
    snapshot = {
        "_generated_at": "2026-01-01T00:00:00+00:00", "period_start": "2016-03-26",
        "period_end": "2016-04-24", "rows": [{"label": " =test | name", "units": 0}] * 11,
        "nested": {"event": {"observed_days": 4, "total_demand": None}},
    }
    parameters = {"state": "CA", "product_id": 1, "store_id": None}
    result = build_report("Test report", snapshot, parameters, ["Missing stays blank."])
    assert result == build_report("Test report", snapshot, dict(reversed(list(parameters.items()))),
                                  ["Missing stays blank."])
    csv_text, markdown = result
    records = list(csv.DictReader(io.StringIO(csv_text)))
    assert records[0]["generated_at_utc"] == snapshot["_generated_at"]
    assert json.loads(records[0]["applied_filters"]) == {"state": "CA", "product_id": 1}
    assert records[0]["period_start"] == "2016-03-26"
    assert len([row for row in records if row["section"] == "rows"]) == 11
    assert next(row for row in records if row["section"] == "rows")["label"].startswith("'")
    assert "Showing 10 of 11 rows" in markdown and r"|" in markdown
    assert "Missing stays blank." in markdown


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("path", [
    "seasonality?group_by=bad", "seasonality?days=730&store_id=1",
    "seasonality?days=1096&store_id=1&product_id=2", "event-window?before=2",
    "event-window?event_name=Easter&before=8", "event-window?event_name=Easter&after=-1",
    "event-analysis?event_type=", "snap-analysis?aggregation=yearly",
    "price-intelligence?product_id=1", "price-intelligence?product_id=1&store_id=-2",
])
def test_invalid_requests_do_not_read_database(client, monkeypatch, path):
    read = Mock()
    monkeypatch.setattr(service, "read_sales_statement", read)
    monkeypatch.setattr(prices, "read_sales_statement", read)
    assert client.get(f"/analytics/{path}").status_code == 422
    read.assert_not_called()


def test_seasonality_response_keeps_coverage_and_zero(client, monkeypatch):
    read = Mock(return_value=({"buckets": [BUCKET]}, WINDOW))
    monkeypatch.setattr(service, "read_sales_statement", read)
    response = client.get("/analytics/seasonality?group_by=weekday&store_id=1&category=HOBBIES")
    assert response.status_code == 200, response.text
    assert response.json()["buckets"] == [BUCKET]
    assert read.call_args.args[1] == {"days": 30, "end_date": None, "store_id": 1, "category": "HOBBIES"}
    statement, _ = service.build_seasonality_statement(SeasonalityQuery())
    assert "GROUP BY sale_day" in str(statement)
    assert "COUNT(demand)" in str(statement)


@pytest.mark.parametrize(("path", "capability"), [
    ("event-analysis", "events"), ("snap-analysis", "snap"),
    ("price-intelligence?product_id=1&store_id=1", "pricing"),
])
def test_unsupported_metadata_is_reported_safely(client, monkeypatch, path, capability):
    description = service.describe_capabilities({})
    monkeypatch.setattr(service, "get_capabilities", Mock(return_value=description))
    response = client.get(f"/analytics/{path}")
    assert response.status_code == 501 and response.headers["X-Request-ID"]
    assert response.json()["detail"] == description[capability]["detail"]


def test_calendar_dashboard_loads_one_report_and_invalidates_on_filter_change(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from dashboard import api_client
    from dashboard.calendar_intelligence import _capabilities
    from dashboard.catalog_widgets import _catalog_data

    def block_network(*args, **kwargs):
        raise AssertionError("Dashboard tests must not call live services.")

    monkeypatch.setattr("requests.sessions.Session.request", block_network)
    for name, response in {
        "get_catalog_states": {"states": ["CA"]},
        "get_catalog_stores": [{"store_id": 1, "store_code": "CA_1"}],
        "get_catalog_categories": {"categories": ["HOBBIES"]},
        "get_catalog_departments": {"departments": ["HOBBIES_1"]},
        "get_capabilities": service.describe_capabilities({}),
    }.items():
        monkeypatch.setattr(api_client, name, Mock(return_value=response))
    get_report = Mock(return_value={**WINDOW, "group_by": "weekday", "buckets": [BUCKET]})
    price_report = Mock()
    monkeypatch.setattr(api_client, "get_seasonality", get_report)
    monkeypatch.setattr(api_client, "get_price_intelligence", price_report)
    _catalog_data.clear()
    _capabilities.clear()
    try:
        at = AppTest.from_file(
            Path(__file__).resolve().parents[2] / "dashboard" / "app.py", default_timeout=20,
        ).run()
        at.sidebar.radio[0].set_value("Seasonality & Events").run()
        get_report.assert_not_called()
        at.button[0].click().run()
        assert not at.exception and len(at.get("download_button")) == 2
        assert get_report.call_count == 1
        at.selectbox(key="calendar_days").set_value(90).run()
        assert not at.dataframe and not at.get("download_button") and get_report.call_count == 1
        at.selectbox(key="calendar_mode").set_value("Price Intelligence").run()
        assert any("requires sell_prices" in message.value for message in at.info)
        price_report.assert_not_called()
    finally:
        _catalog_data.clear()
        _capabilities.clear()
