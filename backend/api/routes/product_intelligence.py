from typing import Annotated

from fastapi import APIRouter, Query

from backend.api.routes.sales_intelligence import _execute
from backend.api.schemas.product_intelligence import (
    ABCQuery, ABCResponse, DemandSegmentQuery, DemandSegmentResponse,
    ProductComparisonQuery, ProductComparisonResponse, ProductPerformanceQuery,
    ProductRankingQuery, ProductRankingResponse,
)
from backend.services import product_intelligence_service as service

router = APIRouter(prefix="/analytics", tags=["Product Intelligence"])


@router.get("/product-performance", response_model=ProductComparisonResponse)
def product_performance(query: Annotated[ProductPerformanceQuery, Query()]):
    return _execute(service.get_product_comparison, query, [query.product_id])


@router.get("/product-comparison", response_model=ProductComparisonResponse)
def product_comparison(query: Annotated[ProductComparisonQuery, Query()]):
    return _execute(service.get_product_comparison, query, query.product_ids)


@router.get("/product-rankings", response_model=ProductRankingResponse)
def product_rankings(query: Annotated[ProductRankingQuery, Query()]):
    return _execute(service.get_product_rankings, query)


@router.get("/demand-segments", response_model=DemandSegmentResponse)
def demand_segments(query: Annotated[DemandSegmentQuery, Query()]):
    return _execute(service.get_demand_segments, query)


@router.get("/abc-analysis", response_model=ABCResponse)
def abc_analysis(query: Annotated[ABCQuery, Query()]):
    return _execute(service.get_abc_analysis, query)
