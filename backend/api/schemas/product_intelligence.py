from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.sales_intelligence import Aggregation, SalesScope, SalesWindow

ProductID = Annotated[int, Field(gt=0, le=2**31 - 1)]
ProductSort = Literal["top", "bottom", "growth", "decline", "variability", "zero_frequency"]
Segment = Literal["Zero average", "Low demand", "Medium demand", "High demand"]
ABCClass = Literal["A", "B", "C", "Unclassified"]


class ProductPerformanceQuery(SalesScope):
    product_id: ProductID
    aggregation: Aggregation = "weekly"


class ProductComparisonQuery(SalesScope):
    product_ids: list[ProductID] = Field(min_length=1, max_length=5)
    aggregation: Aggregation = "weekly"

    @field_validator("product_ids")
    @classmethod
    def unique_products(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Select distinct product IDs.")
        return values


class ProductPageQuery(SalesScope):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)


class ProductRankingQuery(ProductPageQuery):
    sort: ProductSort = "top"
    minimum_previous_demand: int = Field(default=30, ge=1, le=2**31 - 1)


class DemandSegmentQuery(ProductPageQuery):
    segment: Segment | None = None
    product_id: ProductID | None = None


class ABCQuery(ProductPageQuery):
    classification: ABCClass | None = None


class ProductIdentity(BaseModel):
    product_id: int
    item_id: str
    category: str | None
    department: str | None


class ProductMetrics(ProductIdentity):
    total_demand: int | None
    average_daily_demand: float | None
    average_observed_day_demand: float | None
    previous_demand: int | None
    absolute_change: int | None
    percentage_growth: float | None
    observed_days: int
    previous_observed_days: int
    positive_sales_days: int
    zero_demand_days: int
    zero_demand_frequency: float | None
    daily_stddev: float | None
    coefficient_of_variation: float | None
    contribution_pct: float | None


class ProductTrendPoint(BaseModel):
    product_id: int
    period: date
    total_demand: int | None
    observed_days: int
    expected_days: int


class ProductComparisonResponse(SalesWindow):
    aggregation: Aggregation
    previous_period_start: date
    previous_period_end: date
    products: list[ProductMetrics]
    trend: list[ProductTrendPoint]


class RankedProduct(ProductMetrics):
    rank: int


class ProductPage(SalesWindow):
    total: int
    limit: int
    offset: int


class ProductRankingResponse(ProductPage):
    sort: ProductSort
    minimum_previous_demand: int
    products: list[RankedProduct]


class SegmentSummary(BaseModel):
    segment: Segment
    pair_count: int
    total_demand: int
    contribution_pct: float | None


class SegmentedProduct(ProductIdentity):
    store_id: int
    store_code: str
    segment: Segment
    observed_days: int
    average_observed_day_demand: float
    total_demand: int


class DemandSegmentResponse(ProductPage):
    summary: list[SegmentSummary]
    products: list[SegmentedProduct]


class ABCSummary(BaseModel):
    classification: ABCClass
    product_count: int
    total_demand: int
    contribution_pct: float | None


class ABCProduct(ProductIdentity):
    rank: int
    classification: ABCClass
    observed_days: int
    total_demand: int
    contribution_pct: float | None
    cumulative_pct: float | None


class ABCResponse(ProductPage):
    summary: list[ABCSummary]
    products: list[ABCProduct]
