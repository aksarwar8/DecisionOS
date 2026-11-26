
from datetime import date

from pydantic import BaseModel


class AnalyticsPeriod(BaseModel):
    period_start: date
    period_end: date
    period_days: int
    observed_days: int
    positive_sales_days: int
    average_daily_demand: float
    average_observed_day_demand: float | None


class OverviewResponse(AnalyticsPeriod):
    latest_sales_date: date
    total_demand: int
    active_products: int
    active_stores: int
    sales_days: int


class ProductAnalyticsResponse(AnalyticsPeriod):
    product_id: int
    item_id: str
    category: str | None
    department: str | None
    total_sales: float
    maximum_daily_demand: int
    active_days: int


class StoreAnalyticsResponse(AnalyticsPeriod):
    store_id: int
    store_code: str
    state: str | None
    total_sales: float
    maximum_daily_demand: int
    active_days: int


class TrendDay(BaseModel):
    date: date
    sales_quantity: int


class TrendResponse(AnalyticsPeriod):
    product_id: int
    store_id: int
    days: int
    total_demand: int
    trend: list[TrendDay]
