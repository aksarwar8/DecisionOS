from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas.product_intelligence import ABCQuery, DemandSegmentQuery, ProductRankingQuery
from backend.main import app
from backend.services import product_intelligence_service as service
from backend.services.sales_intelligence_service import SalesQueryTimeout
from src.decisionos.ml.demand_segments import DEMAND_SEGMENTS, DEMAND_SEGMENT_UPPER_BOUNDS

WINDOW = {
    "period_start": date(2016, 3, 26), "period_end": date(2016, 4, 24),
    "period_days": 30, "latest_sales_date": date(2016, 4, 24),
}
PRODUCT = {
    "product_id": 4, "item_id": "HOBBIES_1_004", "category": "HOBBIES", "department": "HOBBIES_1",
    "total_demand": 6, "average_daily_demand": 0.2, "average_observed_day_demand": 3,
    "previous_demand": 0, "absolute_change": 6, "percentage_growth": None, "observed_days": 2,
    "previous_observed_days": 1, "positive_sales_days": 1, "zero_demand_days": 1,
    "zero_demand_frequency": 0.5, "daily_stddev": 4.242640687119285,
    "coefficient_of_variation": 1.414213562373095, "contribution_pct": 60,
}


def test_ranking_sql_binds_user_filters_and_growth_threshold():
    query = ProductRankingQuery(
        sort="growth", state="CA", category="quoted ' category", days=60, minimum_previous_demand=45,
    )
    statement, params = service._ranking_statement(query)
    assert params["minimum"] == 45
    assert params["state"] == "CA"
    assert params["category"] == "quoted ' category"
    sql = str(statement)
    assert params["category"] not in sql
    assert "p.category = :category" in sql and "st.state = :state" in sql
    assert "previous_demand >= :minimum AND percentage_growth > 0" in sql
    assert "ORDER BY percentage_growth DESC, product_id" in sql
    assert "GROUP BY 1, 2, 3" in sql and "STDDEV_SAMP(demand)" in sql


@pytest.mark.parametrize(("sort", "order"), [
    ("top", "total_demand DESC"), ("bottom", "total_demand ASC"),
    ("decline", "percentage_growth ASC"), ("variability", "coefficient_of_variation DESC"),
    ("zero_frequency", "zero_demand_frequency DESC"),
])
def test_ranking_choices_apply_deterministic_order(sort, order):
    sql, _ = service._ranking_statement(ProductRankingQuery(sort=sort))
    assert f"ORDER BY {order}, product_id" in str(sql)


def test_segment_sql_uses_forecast_cutoffs():
    sql, params = service._segments_statement(DemandSegmentQuery())
    assert tuple(params[key] for key in ("zero", "low", "medium")) == DEMAND_SEGMENT_UPPER_BOUNDS
    assert tuple(params["labels"]) == DEMAND_SEGMENTS
    assert "GROUP BY product_id, store_id" in str(sql)


def test_abc_window_precedes_classification_filter_and_offset():
    statement, params = service._abc_statement(ABCQuery(classification="B", offset=20))
    sql = str(statement)
    assert params["classification"] == "B" and params["offset"] == 20
    assert "ORDER BY total_demand DESC, product_id ROWS UNBOUNDED PRECEDING" in sql
    assert sql.index("SUM(total_demand) OVER") < sql.index("c.classification = :classification")
    assert sql.index("c.classification = :classification") < sql.index("OFFSET :offset")


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("path", [
    "product-performance?product_id=0", "product-performance?product_id=1&aggregation=bad",
    "product-comparison", "product-comparison?product_ids=1&product_ids=1",
    "product-comparison?" + "&".join(f"product_ids={i}" for i in range(1, 7)),
    "product-rankings?sort=anything", "product-rankings?minimum_previous_demand=0",
    "abc-analysis?classification=X", "abc-analysis?limit=101", "demand-segments?offset=-1",
    "demand-segments?segment=empty", "product-rankings?days=366",
])
def test_invalid_queries_do_not_reach_database(client, monkeypatch, path):
    read = Mock()
    monkeypatch.setattr(service, "read_sales_statement", read)
    assert client.get(f"/analytics/{path}").status_code == 422
    read.assert_not_called()


def test_comparison_validates_and_preserves_selected_order_and_coverage(client, monkeypatch):
    absent = {**PRODUCT, "product_id": 7, "item_id": "ABSENT", "total_demand": None,
              "observed_days": 0, "zero_demand_frequency": None, "coefficient_of_variation": None}
    read = Mock(return_value=({
        "products": [absent, PRODUCT], "trend": [
            {"product_id": 7, "period": "2016-03-26", "total_demand": None,
             "observed_days": 0, "expected_days": 1},
        ],
    }, WINDOW))
    monkeypatch.setattr(service, "read_sales_statement", read)
    response = client.get("/analytics/product-comparison?product_ids=7&product_ids=4&aggregation=daily")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["previous_period_start"] == "2016-02-25"
    assert payload["previous_period_end"] == "2016-03-25"
    assert [row["product_id"] for row in payload["products"]] == [7, 4]
    assert payload["trend"][0]["total_demand"] is None
    assert payload["products"][1]["coefficient_of_variation"] == pytest.approx(2**0.5)
    assert payload["products"][1]["zero_demand_frequency"] == 0.5
    assert read.call_args.args[1]["product_ids"] == [7, 4]


def test_query_timeout_is_safe(client, monkeypatch):
    monkeypatch.setattr(service, "read_sales_statement", Mock(side_effect=SalesQueryTimeout("private")))
    response = client.get("/analytics/product-performance?product_id=4")
    assert response.status_code == 503
    assert response.headers["X-Request-ID"]
    assert "private" not in response.text


def test_dashboard_only_loads_on_click_and_hides_stale_results(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from dashboard import api_client
    from dashboard.catalog_widgets import _catalog_data

    def block_network(*args, **kwargs):
        raise AssertionError("Dashboard test must not reach live services.")

    monkeypatch.setattr("requests.sessions.Session.request", block_network)
    for name, response in {
        "get_catalog_states": {"states": ["CA"]},
        "get_catalog_stores": [{"store_id": 1, "store_code": "CA_1"}],
        "get_catalog_categories": {"categories": ["HOBBIES"]},
        "get_catalog_departments": {"departments": ["HOBBIES_1"]},
        "get_catalog_products": {
            "products": [PRODUCT, {**PRODUCT, "product_id": 5, "item_id": "HOBBIES_1_005"}],
            "total": 2,
        },
    }.items():
        monkeypatch.setattr(api_client, name, Mock(return_value=response))
    fetch = Mock(return_value={
        **WINDOW, "products": [PRODUCT], "trend": [], "previous_period_start": "2016-02-25",
        "previous_period_end": "2016-03-25",
    })
    comparison = Mock(return_value=fetch.return_value)
    monkeypatch.setattr(api_client, "get_product_performance", fetch)
    monkeypatch.setattr(api_client, "get_product_comparison", comparison)
    _catalog_data.clear()
    try:
        at = AppTest.from_file(
            Path(__file__).resolve().parents[2] / "dashboard" / "app.py", default_timeout=20,
        ).run()
        at.sidebar.radio[0].set_value("Product Intelligence").run()
        at.selectbox(key="pi_drill_product").set_value(4).run()
        fetch.assert_not_called()
        next(button for button in at.button if button.label == "Load product analysis").click().run()
        assert not at.exception and at.dataframe
        assert fetch.call_args.kwargs["product_id"] == 4
        at.selectbox(key="pi_days").set_value(60).run()
        assert not at.exception and not at.dataframe and fetch.call_count == 1
        at.radio(key="pi_mode").set_value("Comparison").run()
        at.selectbox(key="pi_compare_product").set_value(4).run()
        next(button for button in at.button if button.label == "Add product").click().run()
        at.selectbox(key="pi_compare_product").set_value(5).run()
        next(button for button in at.button if button.label == "Add product").click().run()
        comparison.assert_not_called()
        next(button for button in at.button if button.label == "Load product analysis").click().run()
        assert not at.exception and comparison.call_args.kwargs["product_ids"] == (4, 5)
    finally:
        _catalog_data.clear()
