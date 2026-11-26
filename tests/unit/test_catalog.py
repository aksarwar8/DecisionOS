from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.schemas.catalog import ProductCatalogEntry
from backend.main import app
from backend.services import catalog_service
from dashboard import api_client

PRODUCT = {"product_id": 4, "item_id": "HOBBIES_1_004", "category": "HOBBIES",
           "department": "HOBBIES_1"}


@pytest.fixture
def database(monkeypatch):
    connection = Mock()
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=connection)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(catalog_service, "get_engine", lambda: engine)
    return connection


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_product_search_filters_and_pagination_are_bound(client, database):
    database.execute.return_value.mappings.return_value.all.return_value = [{**PRODUCT, "total": 8}]
    response = client.get("/catalog/products", params={
        "search": " 004 ", "category": "HOBBIES", "department": "HOBBIES_1",
        "limit": 2, "offset": 2,
    })
    assert response.status_code == 200
    assert response.json() == {"products": [PRODUCT], "total": 8, "limit": 2, "offset": 2}
    assert response.headers["X-Request-ID"]
    query, params = database.execute.call_args.args
    sql = str(query)
    assert params == {"search": "004", "product_id": 4, "category": "HOBBIES",
                      "department": "HOBBIES_1", "limit": 2, "offset": 2}
    assert "strpos(lower(item_id), lower(:search))" in sql
    assert "OR id = :product_id" in sql
    assert "category = :category AND department = :department" in sql
    assert "ORDER BY exact_id_match DESC, item_id, product_id" in sql
    assert "HOBBIES" not in sql
    assert "sales" not in sql


@pytest.mark.parametrize("term", ["hobbies_1", "%_'", "3000000000"])
def test_text_search_is_literal_and_does_not_bind_an_invalid_integer(database, term):
    database.execute.return_value.mappings.return_value.all.return_value = [
        {"product_id": None, "total": 0},
    ]
    assert catalog_service.list_products(search=term)["products"] == []
    query, params = database.execute.call_args.args
    assert params["search"] == term
    assert "product_id" not in params
    assert term not in str(query)


@pytest.mark.parametrize("total", [0, 3])
def test_empty_page_retains_total_count(client, database, total):
    database.execute.return_value.mappings.return_value.all.return_value = [
        {"product_id": None, "total": total},
    ]
    response = client.get("/catalog/products?offset=100")
    assert response.status_code == 200
    assert response.json() == {"products": [], "total": total, "limit": 50, "offset": 100}


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "offset=2147483648"])
def test_invalid_page_is_rejected_at_the_api_boundary(client, database, query):
    assert client.get(f"/catalog/products?{query}").status_code == 422
    database.execute.assert_not_called()


def test_store_list_uses_state_filter_and_business_code(client, database):
    entries = [{"store_id": 1, "store_code": "CA_1", "state": "CA"}]
    database.execute.return_value.mappings.return_value.all.return_value = entries
    response = client.get("/catalog/stores?state=CA")
    assert response.status_code == 200
    assert response.json() == entries
    query, params = database.execute.call_args.args
    assert params == {"state": "CA"}
    assert "store_id AS store_code" in str(query)
    assert "state = :state" in str(query)


@pytest.mark.parametrize(("route", "field", "values"), [
    ("/catalog/categories", "categories", ["HOBBIES"]),
    ("/catalog/departments?category=HOBBIES", "departments", ["HOBBIES_1", "HOBBIES_2"]),
    ("/catalog/states", "states", ["CA", "TX"]),
])
def test_filter_options(client, database, route, field, values):
    database.execute.return_value.scalars.return_value.all.return_value = values
    response = client.get(route)
    assert response.status_code == 200
    assert response.json() == {field: values}
    if field == "departments":
        query, params = database.execute.call_args.args
        assert params == {"category": "HOBBIES"}
        assert "category = :category" in str(query)


def test_database_failure_uses_generic_api_error(client, database):
    database.execute.side_effect = RuntimeError("private SQL failure")
    response = client.get("/catalog/stores")
    assert response.status_code == 500
    assert response.json() == {
        "detail": "An internal error occurred.",
        "request_id": response.headers["X-Request-ID"],
    }


def test_response_schema_accepts_missing_metadata_and_requires_positive_id():
    entry = {**PRODUCT, "category": None, "department": None}
    assert ProductCatalogEntry.model_validate(entry).category is None
    with pytest.raises(ValidationError, match="product_id"):
        ProductCatalogEntry.model_validate({**entry, "product_id": 0})


def test_dashboard_client_uses_configured_base_url_and_passes_page_parameters(monkeypatch):
    monkeypatch.setattr(api_client, "_base_url", lambda: "http://example.invalid")
    get = Mock()
    monkeypatch.setattr(api_client.requests, "get", get)
    api_client.get_catalog_products(search="HOBBIES", offset=50)
    get.assert_called_once_with(
        "http://example.invalid/catalog/products",
        params={"search": "HOBBIES", "limit": 50, "offset": 50},
        timeout=10,
    )
    get.return_value.raise_for_status.assert_called_once()
