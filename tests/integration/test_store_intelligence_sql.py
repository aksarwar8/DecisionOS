import pytest
from sqlalchemy import text

from backend.api.schemas.store_intelligence import (
    MatrixQuery, MerchandiseQuery, PerformanceQuery, StoreComparisonQuery, StoreRankingQuery,
)
from backend.services import store_intelligence_service as service

pytestmark = pytest.mark.integration


def _execute(connection, statement):
    sql, params = statement
    # Replace table references inside this statement with a tiny read-only fixture.
    fixture = f"""
        WITH calendar(id,date) AS (
            SELECT d, DATE '2021-01-01' + (d - 1) FROM generate_series(1, 7) d
        ), products(id,item_id,category,department) AS (
            VALUES (1, 'ITEM_1', 'FOODS', 'FOODS_1'), (2, 'ITEM_2', 'FOODS', 'FOODS_2'),
                   (3, 'ITEM_3', NULL, NULL), (4, 'ITEM_4', 'HOBBIES', 'HOBBIES_1')
        ), stores(id,store_id,state) AS (
            VALUES (1, 'CA_1', 'CA'), (2, 'CA_2', 'CA'), (3, 'TX_1', 'TX'), (4, 'WI_1', 'WI')
        ), sales(product_id,store_id,calendar_id,sales_quantity) AS (
            VALUES (1,1,1,2),(2,1,2,0),(1,2,1,0),(4,3,3,3),
                   (1,1,4,4),(2,1,4,0),(1,1,5,2),(3,1,6,0),(1,2,4,6),(4,3,5,3)
        ), {str(sql).strip()[5:]}
    """
    return connection.execute(text(fixture), params).mappings().one()


@pytest.mark.parametrize("aggregation", ["daily", "weekly", "monthly"])
def test_store_comparison_coverage_and_scope_denominator(connection, aggregation):
    query = StoreComparisonQuery(days=3, store_ids=[1, 2, 4], aggregation=aggregation)
    result = _execute(connection, service.build_entity_statement(query, "store", selected=query.store_ids))
    assert str(result["period_start"]) == "2021-01-04"
    assert str(result["period_end"]) == "2021-01-06"
    first, second, missing = result["entities"]
    assert first["total_demand"] == 6 and first["previous_demand"] == 2
    assert first["absolute_change"] == 4 and first["percentage_growth"] == 200
    assert first["average_daily_demand"] == 2 and first["contribution_pct"] == 50
    assert first["observed_days"] == 3 and first["positive_demand_days"] == 2
    assert first["observed_products"] == 3 and first["positive_demand_products"] == 1
    assert second["percentage_growth"] is None and second["previous_demand"] == 0
    assert missing["total_demand"] is None and missing["observed_days"] == 0
    for row in result["entities"]:
        points = [point for point in result["trend"] if point["group_id"] == row["group_id"]]
        assert sum(point["expected_days"] for point in points) == 3
        assert sum(point["observed_days"] for point in points) == row["observed_days"]
    unknown = next(row for row in result["composition"] if row["category"] is None)
    assert unknown["total_demand"] == 0 and unknown["contribution_pct"] == 0


def test_store_ranking_and_state_rollup(connection):
    query = StoreRankingQuery(days=3, state="CA", sort="top")
    result = _execute(connection, service.build_entity_statement(query, "store", ranking=True))
    assert [(row["group_id"], row["rank"]) for row in result["entities"]] == [(1, 1), (2, 2)]
    query = StoreRankingQuery(days=3, sort="growth")
    result = _execute(connection, service.build_entity_statement(query, "store", ranking=True))
    assert [row["group_id"] for row in result["entities"]] == [1]
    states = _execute(connection, service.build_entity_statement(PerformanceQuery(days=3), "state"))["entities"]
    ca, tx, wi = states
    assert ca["total_demand"] == 12 and ca["observed_stores"] == ca["store_count"] == 2
    assert ca["observed_products"] == 3 and ca["average_demand_per_observed_store"] == 6
    assert ca["contribution_pct"] == 80
    assert tx["percentage_growth"] == 0 and wi["percentage_growth"] is None
    assert wi["store_count"] == 1 and wi["observed_stores"] == 0


def test_department_drilldown_and_single_store_share(connection):
    query = MerchandiseQuery(days=3, category="FOODS", state="CA", group_by="department")
    result = _execute(connection, service.build_entity_statement(query, "department"))
    first, second = result["entities"]
    assert first["group_id"] == "FOODS_1" and first["total_demand"] == 12
    assert first["contribution_pct"] == 100 and first["positive_demand_products"] == 1
    assert second["total_demand"] == 0 and second["observed_products"] == 1
    query = PerformanceQuery(days=3, store_id=1)
    result = _execute(connection, service.build_entity_statement(query, "store", drill=1))
    assert result["entities"][0]["contribution_pct"] == 40


@pytest.mark.parametrize("dimension", ["store_category", "store_department", "state_category"])
def test_matrix_distinguishes_missing_and_observed_zero(connection, dimension):
    row = _execute(connection, service.build_matrix_statement(MatrixQuery(days=3, dimensions=dimension)))
    geo = "CA" if dimension.startswith("state") else "CA_1"
    cells = {cell["merchandise_id"]: cell for cell in row["cells"] if cell["geography_label"] == geo}
    missing = cells["HOBBIES_1" if dimension.endswith("department") else "HOBBIES"]
    assert missing["total_demand"] is None and missing["contribution_pct"] is None
    assert cells[None]["total_demand"] == cells[None]["contribution_pct"] == 0
    assert cells[None]["percentage_growth"] is None
    assert cells["FOODS_1" if dimension.endswith("department") else "FOODS"]["contribution_pct"] == 100
