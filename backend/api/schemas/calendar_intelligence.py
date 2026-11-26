from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from backend.api.schemas.sales_intelligence import Aggregation, SalesFilters, SalesWindow

SeasonalGroup = Literal["weekday", "month", "year", "year_month", "weekday_weekend"]
PositiveID = Annotated[int, Field(gt=0, le=2**31 - 1)]


class SeasonalityQuery(SalesFilters):
    days: int = Field(default=30, ge=1, le=1095)
    group_by: SeasonalGroup = "weekday"

    @model_validator(mode="after")
    def limit_broad_windows(self):
        if self.days > 365 and (self.product_id is None or self.store_id is None):
            raise ValueError("Windows over 365 days require both a product and a store.")
        return self


class EventQuery(SalesFilters):
    event_name: str | None = Field(default=None, min_length=1, max_length=100)
    event_type: str | None = Field(default=None, min_length=1, max_length=100)


class EventWindowQuery(EventQuery):
    before: int = Field(default=3, ge=0, le=7)
    after: int = Field(default=3, ge=0, le=7)

    @model_validator(mode="after")
    def require_event_selection(self):
        if self.event_name is None and self.event_type is None:
            raise ValueError("Select an event name or type for an event-relative window.")
        return self


class SnapQuery(SalesFilters):
    aggregation: Aggregation = "weekly"


class PriceQuery(SalesFilters):
    product_id: PositiveID
    store_id: PositiveID


class Capability(BaseModel):
    available: bool
    detail: str


class CapabilitiesResponse(BaseModel):
    events: Capability
    snap: Capability
    pricing: Capability


class DailyStatistics(BaseModel):
    total_demand: int | None
    average_daily_demand: float | None
    observed_days: int
    expected_days: int
    positive_demand_days: int
    zero_demand_days: int
    coverage_pct: float | None
    daily_stddev: float | None


class SeasonalBucket(DailyStatistics):
    label: str
    partial_calendar_period: bool


class SeasonalityResponse(SalesWindow):
    group_by: SeasonalGroup
    buckets: list[SeasonalBucket]


class EventCatalogEntry(BaseModel):
    name: str
    event_type: str | None
    occurrence_days: int


class EventCatalogResponse(BaseModel):
    calendar_start: date | None
    calendar_end: date | None
    events: list[EventCatalogEntry]


class EventComparison(BaseModel):
    matched_observed_days: int
    comparable_baseline_days: int
    matched_average_demand: float | None
    standardized_baseline_average: float | None
    absolute_difference: float | None
    percentage_difference: float | None


class EventAnalysisResponse(SalesWindow):
    event_name: str | None
    event_type: str | None
    event: DailyStatistics
    non_event_baseline: DailyStatistics
    comparison: EventComparison


class EventOffset(DailyStatistics):
    offset: int
    comparison: EventComparison


class EventWindowResponse(SalesWindow):
    event_name: str | None
    event_type: str | None
    occurrence_days: int
    offsets: list[EventOffset]


class SnapStatistics(BaseModel):
    status: Literal["SNAP", "Non-SNAP"]
    total_demand: int | None
    observed_store_days: int
    average_demand_per_observed_store_day: float | None


class SnapTrendPoint(SnapStatistics):
    period: date


class SnapResponse(SalesWindow):
    aggregation: Aggregation
    groups: list[SnapStatistics]
    absolute_difference: float | None
    percentage_difference: float | None
    excluded_observed_store_days: int
    trend: list[SnapTrendPoint]


class PriceWeek(BaseModel):
    week_start: date
    week_key: int
    unit_price: float | None
    total_demand: int | None
    observed_days: int
    expected_days: int
    price_conflict: bool


class PriceChange(BaseModel):
    week_start: date
    previous_price: float
    current_price: float
    previous_average_daily_demand: float | None
    current_average_daily_demand: float | None
    average_daily_demand_difference: float | None


class PriceResponse(SalesWindow):
    product_id: int
    store_id: int
    total_demand: int | None
    observed_days: int
    matched_days: int
    matched_demand: int | None
    match_coverage_pct: float | None
    estimated_sales_value: float | None
    weighted_average_unit_price: float | None
    minimum_unit_price: float | None
    maximum_unit_price: float | None
    comparable_price_week_pairs: int
    price_change_frequency_pct: float | None
    price_demand_correlation: float | None
    correlation_week_count: int
    weekly: list[PriceWeek]
    changes: list[PriceChange]
