# DecisionOS V1.2.1 catalog guide

The forecast and analytics APIs use numeric IDs to identify a product-store pair. Previously, dashboard users had to find those IDs elsewhere and type them in. Now they can browse item codes such as `HOBBIES_1_004` and store codes such as `CA_1`. The dashboard keeps the numerical IDs behind those labels and passes them to the existing APIs.

## Where the data comes from

| PostgreSQL table | Columns used | API names |
|---|---|---|
| `products` | `id`, `item_id`, `category`, `department` | `product_id`, `item_id`, `category`, `department` |
| `stores` | `id`, `store_id`, `state` | `store_id`, `store_code`, `state` |

In PostgreSQL, `stores.store_id` is a business code. Across the API, `store_id` means the numeric primary key and `store_code` holds that business code. Category, department and state can be null. Catalog entries preserve those nulls, while filter menus list only available non-null values. The catalog uses item codes as product labels. Its queries only read the two dimension tables.

## Service and SQL

Start with [catalog_service.py](../../backend/services/catalog_service.py). It uses the existing `get_engine()` connection utility and SQLAlchemy's `text()` with bound parameters. The optional product filters append fixed SQL expressions to the statement. The actual values are passed separately in a dictionary.

```sql
strpos(lower(item_id), lower(:search)) > 0
category = :category
department = :department
```

The search is a case-insensitive substring of the item code. Characters such as `%` and `_` are literal. When the trimmed search string is also a valid positive PostgreSQL integer, the query includes an exact `id` match and puts that row first. Active category and department filters still apply. Store filtering compares the business state code exactly.

Product pages default to 50 entries and accept a limit from 1 to 100. An offset of 50 skips the first 50 rows in the filtered order. Rows sort by exact numeric match priority, item code, then numeric ID. The total counts every match in the same SQL statement as the page, so both values describe the same database snapshot. The query starts from the count and left joins the page, preserving the count when an offset runs past the end. An empty page is a normal response.

## API contract

[catalog.py in the schemas package](../../backend/api/schemas/catalog.py) declares the entry and response models. [catalog.py in the routes package](../../backend/api/routes/catalog.py) validates query parameters and calls the service. [main.py](../../backend/main.py) registers the router. Invalid query parameters receive FastAPI's 422 response. Unexpected database errors use the existing generic 500 response and request ID.

| Endpoint | Query parameters | Response |
|---|---|---|
| `GET /catalog/products` | `search`, `category`, `department`, `limit`, `offset` | `products`, `total`, `limit`, `offset` |
| `GET /catalog/stores` | `state` | List of store entries |
| `GET /catalog/categories` | None | `categories` |
| `GET /catalog/departments` | Optional `category` | `departments` |
| `GET /catalog/states` | None | `states` |

For example, the live API returned this page for `GET /catalog/products?search=4&limit=1`. The total includes substring matches too.

```json
{
  "products": [
    {"product_id": 4, "item_id": "HOBBIES_1_004", "category": "HOBBIES", "department": "HOBBIES_1"}
  ],
  "total": 842,
  "limit": 1,
  "offset": 0
}
```

## Dashboard flow

[api_client.py](../../dashboard/api_client.py) exposes the catalog endpoints using the configured API base URL, a 10-second timeout, and the existing HTTP status-check convention. [catalog_widgets.py](../../dashboard/catalog_widgets.py) renders the selectors for both pages in [app.py](../../dashboard/app.py).

1. The dashboard loads categories and states. Picking a category narrows the department list and the product query.
2. The current filters and search determine which 50-row product page is requested. Previous and Next change the offset. Filter changes reset the offset and clear the product selection. A page change also clears it.
3. The Product and Store dropdowns display business codes while their selected values remain numeric IDs. A store selection is cleared if it is absent from the chosen state. Empty or failed catalog lookups disable the forecast or analytics action.
4. A user must click Generate Forecast or Load Business Analytics to make the existing request. The existing result keys include both IDs and the selected horizon or period. Changing those inputs clears the old result.

Successful catalog responses are cached by resource and query parameters for up to 120 seconds, with a maximum of 128 entries. A request or JSON decoding exception does not produce a cached result. Forecast and analytics responses continue to use their existing session-state behavior.

## Changes and verification

- Added the catalog service, schemas, routes, reusable dashboard widgets, this guide, and [catalog tests](../../tests/unit/test_catalog.py).
- Updated the FastAPI router registration, dashboard API client, and the two dashboard pages.
- `python -m pytest -q` passed 62 cases, including the 45 existing cases. `python -m ruff check src backend dashboard tests` passed. Catalog unit tests mocked the database connection.
- A separate mocked Streamlit AppTest exercised pagination, cache reuse, numeric ID forwarding, button-driven requests, and clearing old results after filters changed.
- Bounded HTTP GETs against the existing API on port 8000 used live PostgreSQL. They verified 3,049 products and 10 stores, consecutive pages, a 416-item filtered department, case-insensitive item-code search, exact ID priority, and empty results. Requests measured approximately 0.055–0.488 seconds. For example, the filtered product page took 0.060 seconds and the full store list took 0.055 seconds. No sales aggregation or schema change was required.

## Concepts to study

Read the service, route, and widgets in that order. Separate business codes from relational keys so UI labels can change without changing API identifiers. Bind values in SQL to keep input separate from query syntax. Use stable ordering to make offset pagination predictable. A page and its count share one snapshot here, although edits between separate page requests can still shift offsets. The catalog cache trades a short freshness window for fewer repeated requests. Null metadata stays visible in unfiltered lists and cannot be picked as a dedicated filter in this version. A live browser walkthrough remains unverified.
