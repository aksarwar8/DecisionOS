from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Aggregation = Literal["daily", "weekly", "monthly"]
Dimension = Literal["category", "department", "store", "state"]
RankEntity = Literal["product", "store"]
RankOrder = Literal["top", "bottom"]
ReportView = Literal["executive", "sales"]


class SalesScope(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    end_date: date | None = Field(default=None, ge=date(2, 1, 1))
    store_id: int | None = Field(default=None, gt=0, le=2**31 - 1)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    department: str | None = Field(default=None, min_length=1, max_length=100)


class SalesFilters(SalesScope):
    product_id: int | None = Field(default=None, gt=0, le=2**31 - 1)


class SalesWindow(BaseModel):
    period_start: date
    period_end: date
    period_days: int
    latest_sales_date: date


class PeriodDemand(BaseModel):
    start: date
    end: date
    total_demand: int | None
    observed_days: int
    missing_days: int


class GrowthResult(BaseModel):
    current: PeriodDemand
    previous: PeriodDemand
    absolute_change: int | None
    percentage_change: float | None


class GrowthResponse(SalesWindow):
    growth: GrowthResult


class TrendPoint(BaseModel):
    period: date
    total_demand: int
    observed_days: int


class SalesTrendResponse(SalesWindow):
    aggregation: Aggregation
    trend: list[TrendPoint]


class BreakdownEntry(BaseModel):
    group_id: int | str | None
    label: str
    total_demand: int
    percentage_contribution: float | None
    observation_count: int


class BreakdownResponse(SalesWindow):
    group_by: Dimension
    breakdown: list[BreakdownEntry]


class RankedEntry(BaseModel):
    rank: int
    entity_id: int
    code: str
    total_demand: int
    observation_count: int


class RankingsResponse(SalesWindow):
    entity: RankEntity
    order: RankOrder
    rankings: list[RankedEntry]


class SalesReportResponse(GrowthResponse, SalesTrendResponse):
    average_daily_demand: float | None
    active_products: int | None
    active_stores: int
    breakdowns: dict[Dimension, list[BreakdownEntry]]
    top_products: list[RankedEntry]
    top_stores: list[RankedEntry]
