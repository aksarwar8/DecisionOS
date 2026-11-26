
import requests


from src.decisionos.config import get_settings


def _base_url() -> str:
    return get_settings().api_base_url.rstrip("/")


def get_health():
    response = requests.get(
        f"{_base_url()}/health",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_model_info():
    response = requests.get(
        f"{_base_url()}/model/info",
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_model_metrics():
    response = requests.get(
        f"{_base_url()}/model/metrics",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_model_runs(limit: int = 20):
    response = requests.get(
        f"{_base_url()}/model/runs",
        params={"limit": limit},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_model_registry():
    response = requests.get(
        f"{_base_url()}/model/registry",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def generate_forecast(
    product_id: int,
    store_id: int,
    horizon: int,
):
    payload = {
        "product_id": product_id,
        "store_id": store_id,
        "horizon": horizon,
    }

    response = requests.post(
        f"{_base_url()}/forecast/",
        json=payload,
        timeout=120,
    )

    response.raise_for_status()
    return response.json()


def get_product_analytics(
    product_id: int,
    days: int = 90,
):
    response = requests.get(
        f"{_base_url()}/analytics/products/{product_id}",
        params={"days": days},
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_store_analytics(
    store_id: int,
    days: int = 90,
):
    response = requests.get(
        f"{_base_url()}/analytics/stores/{store_id}",
        params={"days": days},
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_demand_trends(
    product_id: int,
    store_id: int,
    days: int = 90,
):
    response = requests.get(
        f"{_base_url()}/analytics/trends",
        params={
            "product_id": product_id,
            "store_id": store_id,
            "days": days,
        },
        timeout=30,
    )

    response.raise_for_status()
    return response.json()



def get_platform_overview(days: int = 90):
    response = requests.get(
        f"{_base_url()}/analytics/overview",
        params={"days": days},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _get_catalog(resource: str, **params):
    response = requests.get(
        f"{_base_url()}/catalog/{resource}",
        params={key: value for key, value in params.items() if value is not None},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_catalog_products(*, search=None, category=None, department=None, limit=50, offset=0):
    return _get_catalog(
        "products", search=search, category=category, department=department,
        limit=limit, offset=offset,
    )


def get_catalog_stores(*, state=None):
    return _get_catalog("stores", state=state)


def get_catalog_categories():
    return _get_catalog("categories")


def get_catalog_departments(*, category=None):
    return _get_catalog("departments", category=category)


def get_catalog_states():
    return _get_catalog("states")


def _get_sales_analysis(resource, **params):
    response = requests.get(
        f"{_base_url()}/analytics/{resource}",
        params={key: value for key, value in params.items() if value is not None},
        timeout=(3, 30),
    )
    response.raise_for_status()
    return response.json()


def get_sales_growth(**filters):
    return _get_sales_analysis("growth", **filters)


def get_sales_trend(*, aggregation="daily", **filters):
    return _get_sales_analysis("sales-trend", aggregation=aggregation, **filters)


def get_sales_breakdown(*, group_by="category", **filters):
    return _get_sales_analysis("breakdown", group_by=group_by, **filters)


def get_sales_rankings(*, entity="product", order="top", limit=5, **filters):
    return _get_sales_analysis("rankings", entity=entity, order=order, limit=limit, **filters)


def get_sales_report(*, view="sales", aggregation="weekly", **filters):
    return _get_sales_analysis("sales-report", view=view, aggregation=aggregation, **filters)
