from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from backend.api.schemas.sales_intelligence import (
    Aggregation, BreakdownResponse, Dimension, GrowthResponse, RankEntity,
    RankOrder, RankingsResponse, ReportView, SalesFilters, SalesReportResponse,
    SalesTrendResponse,
)
from backend.services import sales_intelligence_service as service
from backend.services.analytics_service import AnalyticsNotFoundError

router = APIRouter(prefix="/analytics", tags=["Sales Intelligence"])
Filters = Annotated[SalesFilters, Query()]


class TrendQuery(SalesFilters):
    aggregation: Aggregation = "daily"


class BreakdownQuery(SalesFilters):
    group_by: Dimension = "category"


class RankingsQuery(SalesFilters):
    entity: RankEntity = "product"
    order: RankOrder = "top"
    limit: int = Field(default=5, ge=1, le=50)


class ReportQuery(SalesFilters):
    view: ReportView = "sales"
    aggregation: Aggregation = "weekly"


def _execute(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except AnalyticsNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except service.SalesWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except service.SalesQueryTimeout as error:
        raise HTTPException(
            status_code=503, detail="Analysis exceeded the time limit. Try a shorter period or narrower filters.",
        ) from error


@router.get("/growth", response_model=GrowthResponse)
def growth(filters: Filters):
    return _execute(service.get_growth, filters)


@router.get("/sales-trend", response_model=SalesTrendResponse)
def sales_trend(filters: Annotated[TrendQuery, Query()]):
    return _execute(service.get_sales_trend, filters, filters.aggregation)


@router.get("/breakdown", response_model=BreakdownResponse)
def breakdown(filters: Annotated[BreakdownQuery, Query()]):
    return _execute(service.get_breakdown, filters, filters.group_by)


@router.get("/rankings", response_model=RankingsResponse)
def rankings(filters: Annotated[RankingsQuery, Query()]):
    return _execute(service.get_rankings, filters, filters.entity, filters.order, filters.limit)


@router.get("/sales-report", response_model=SalesReportResponse)
def sales_report(filters: Annotated[ReportQuery, Query()]):
    return _execute(service.get_sales_report, filters, filters.view, filters.aggregation)
