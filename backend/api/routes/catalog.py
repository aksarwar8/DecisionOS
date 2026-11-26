from fastapi import APIRouter, Query

from backend.api.schemas.catalog import (
    CategoryList,
    DepartmentList,
    ProductCatalogPage,
    StateList,
    StoreCatalogEntry,
)
from backend.services import catalog_service

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/products", response_model=ProductCatalogPage)
def products(
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, min_length=1, max_length=100),
    department: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=catalog_service.MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0, le=catalog_service.MAX_OFFSET),
):
    return catalog_service.list_products(
        search=search, category=category, department=department, limit=limit, offset=offset,
    )


@router.get("/stores", response_model=list[StoreCatalogEntry])
def stores(state: str | None = Query(default=None, min_length=1, max_length=100)):
    return catalog_service.list_stores(state=state)


@router.get("/categories", response_model=CategoryList)
def categories():
    return {"categories": catalog_service.list_categories()}


@router.get("/departments", response_model=DepartmentList)
def departments(category: str | None = Query(default=None, min_length=1, max_length=100)):
    return {"departments": catalog_service.list_departments(category=category)}


@router.get("/states", response_model=StateList)
def states():
    return {"states": catalog_service.list_states()}
