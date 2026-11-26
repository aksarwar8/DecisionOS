from typing import Annotated

from fastapi import APIRouter, Query

from backend.api.routes.sales_intelligence import _execute
from backend.api.schemas.store_intelligence import (
    DemandMatrixResponse, EntityReport, MatrixQuery, MerchandiseQuery, PerformanceQuery,
    StoreComparisonQuery, StorePerformanceQuery, StoreRankingQuery,
)
from backend.services import store_intelligence_service as service

router = APIRouter(prefix="/analytics", tags=["Store and Category Intelligence"])


@router.get("/store-performance", response_model=EntityReport)
def store_performance(query: Annotated[StorePerformanceQuery, Query()]):
    return _execute(service.get_entity_report, query, "store", drill=query.store_id)


@router.get("/store-rankings", response_model=EntityReport)
def store_rankings(query: Annotated[StoreRankingQuery, Query()]):
    return _execute(service.get_entity_report, query, "store", ranking=True)


@router.get("/store-comparison", response_model=EntityReport)
def store_comparison(query: Annotated[StoreComparisonQuery, Query()]):
    return _execute(service.get_entity_report, query, "store", selected=query.store_ids)


@router.get("/state-performance", response_model=EntityReport)
def state_performance(query: Annotated[PerformanceQuery, Query()]):
    return _execute(service.get_entity_report, query, "state")


@router.get("/category-performance", response_model=EntityReport)
def category_performance(query: Annotated[MerchandiseQuery, Query()]):
    return _execute(service.get_entity_report, query, query.group_by)


@router.get("/demand-matrix", response_model=DemandMatrixResponse)
def demand_matrix(query: Annotated[MatrixQuery, Query()]):
    return _execute(service.get_matrix, query)
