import pytest
from sqlalchemy import text

from backend.api.schemas.product_intelligence import ABCQuery, DemandSegmentQuery, ProductComparisonQuery
from backend.services import product_intelligence_service as service
from src.decisionos.data.extract import get_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def connection():
    with get_engine().connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        yield conn


def _fixture_statement(rows, statement):
    # The CTEs shadow the real tables for this statement only.
    return text(f"""
        WITH calendar(id,date) AS (
            SELECT d, DATE '2021-01-01' + (d - 1) FROM generate_series(1, 7) d
        ), products(id,item_id,category,department) AS (
            SELECT id, 'ITEM_' || id, 'CAT', 'DEPT' FROM generate_series(1, 6) id
        ), stores(id,store_id,state) AS (
            VALUES (1, 'CA_1', 'CA'), (2, 'CA_2', 'CA')
        ), sales(product_id,store_id,calendar_id,sales_quantity) AS (VALUES {rows}),
        {str(statement).strip()[5:]}
    """)


@pytest.mark.parametrize("aggregation", ["daily", "weekly", "monthly"])
def test_daily_granularity_and_comparison_coverage(connection, aggregation):
    query = ProductComparisonQuery(days=3, product_ids=[3, 1, 2, 4], aggregation=aggregation)
    statement, params = service._detail_statement(query, query.product_ids)
    rows = "(1,1,1,0),(1,1,4,2),(1,2,4,4),(1,1,5,0),(2,1,6,4),(4,1,6,0)"
    result = connection.execute(_fixture_statement(rows, statement), params).mappings().one()
    assert str(result["period_end"]) == "2021-01-06"
    absent, product, no_prior, zero = result["products"]
    assert [row["product_id"] for row in result["products"]] == [3, 1, 2, 4]
    assert absent["total_demand"] is None and absent["observed_days"] == 0
    assert product["total_demand"] == 6
    assert product["average_daily_demand"] == 2 and product["average_observed_day_demand"] == 3
    assert product["previous_demand"] == 0 and product["absolute_change"] == 6
    assert product["percentage_growth"] is None and no_prior["previous_demand"] is None
    assert product["observed_days"] == 2 and product["zero_demand_frequency"] == 0.5
    assert product["daily_stddev"] == pytest.approx(18**0.5)
    assert product["coefficient_of_variation"] == pytest.approx(2**0.5)
    assert product["contribution_pct"] == 60
    assert zero["total_demand"] == 0 and zero["zero_demand_frequency"] == 1
    assert zero["coefficient_of_variation"] is None and no_prior["daily_stddev"] is None
    trend = [row for row in result["trend"] if row["product_id"] == 3]
    assert sum(row["expected_days"] for row in trend) == 3
    assert all(row["observed_days"] == 0 and row["total_demand"] is None for row in trend)


def test_exact_forecast_segment_thresholds(connection):
    query = DemandSegmentQuery(days=1)
    statement, params = service._segments_statement(query)
    rows = "(1,1,1,0),(2,1,1,1),(3,1,1,2),(4,1,1,5),(5,1,1,6)"
    result = connection.execute(_fixture_statement(rows, statement), params).mappings().one()
    assert [row["segment"] for row in result["products"]] == [
        "High demand", "Medium demand", "Medium demand", "Low demand", "Zero average",
    ]
    assert [row["pair_count"] for row in result["summary"]] == [1, 1, 2, 1]


def test_abc_boundary_and_zero_universe(connection):
    query = ABCQuery(days=1, limit=2, offset=1)
    statement, params = service._abc_statement(query)
    rows = "(1,1,1,80),(2,1,1,15),(3,1,1,5),(4,1,1,0),(5,1,1,0)"
    result = connection.execute(_fixture_statement(rows, statement), params).mappings().one()
    assert [(row["classification"], row["cumulative_pct"]) for row in result["products"]] == [
        ("B", 95), ("C", 100),
    ]
    assert [row["product_count"] for row in result["summary"]] == [1, 1, 3, 0]
    rows = "(1,1,1,0),(2,1,1,0)"
    result = connection.execute(_fixture_statement(rows, statement), params).mappings().one()
    assert result["products"][0]["classification"] == "Unclassified"
    assert result["products"][0]["cumulative_pct"] is None
