from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.sales_intelligence import Aggregation, SalesScope, SalesWindow

StoreID = Annotated[int, Field(gt=0, le=2**31 - 1)]
StoreSort = Literal["top", "bottom", "growth", "decline", "average"]
Merchandise = Literal["category", "department"]
MatrixDimension = Literal["store_category", "store_department", "state_category"]


class PerformanceQuery(SalesScope):
    aggregation: Aggregation = "weekly"


class StorePerformanceQuery(PerformanceQuery):
    store_id: StoreID


class StoreComparisonQuery(PerformanceQuery):
    store_ids: list[StoreID] = Field(min_length=1, max_length=5)

    @field_validator("store_ids")
    @classmethod
    def unique_stores(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Select distinct stores.")
        return values


class MerchandiseQuery(PerformanceQuery):
    group_by: Merchandise = "category"


class StoreRankingQuery(SalesScope):
    sort: StoreSort = "top"
    limit: int = Field(default=10, ge=1, le=50)


class MatrixQuery(SalesScope):
    dimensions: MatrixDimension = "store_category"


class ComparableWindow(SalesWindow):
    previous_period_start: date
    previous_period_end: date


class EntityPerformance(BaseModel):
    group_id: int | str | None
    label: str
    store_id: int | None = None
    store_code: str | None = None
    state: str | None = None
    total_demand: int | None
    previous_demand: int | None
    absolute_change: int | None
    percentage_growth: float | None
    average_daily_demand: float | None
    observed_days: int
    previous_observed_days: int
    positive_demand_days: int
    observed_products: int
    positive_demand_products: int
    store_count: int | None = None
    observed_stores: int | None = None
    average_demand_per_observed_store: float | None = None
    contribution_pct: float | None
    rank: int | None = None


class EntityTrendPoint(BaseModel):
    group_id: int | str | None
    label: str
    period: date
    total_demand: int | None
    observed_days: int
    expected_days: int


class CategoryComposition(BaseModel):
    group_id: int | str | None
    group_label: str
    category: str | None
    category_label: str
    total_demand: int
    contribution_pct: float | None


class EntityReport(ComparableWindow):
    group_by: Literal["store", "state", "category", "department"]
    aggregation: Aggregation | None = None
    entities: list[EntityPerformance]
    trend: list[EntityTrendPoint]
    composition: list[CategoryComposition]


class MatrixCell(BaseModel):
    geography_id: int | str | None
    geography_label: str
    merchandise_id: str | None
    merchandise_label: str
    total_demand: int | None
    previous_demand: int | None
    contribution_pct: float | None
    percentage_growth: float | None


class DemandMatrixResponse(ComparableWindow):
    dimensions: MatrixDimension
    cells: list[MatrixCell]
