
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    horizon: Literal[7, 14, 28] = 7
    method: Literal["hybrid", "tsb", "moving_average", "seasonal_naive"] = "hybrid"


class ForecastDay(BaseModel):
    date: date
    demand_segment: str
    selected_model: str
    prediction: float


class ForecastResponse(BaseModel):
    product_id: int
    store_id: int
    horizon: int
    total_predicted_demand: float
    forecasts: list[ForecastDay]
    method: str = "hybrid"
    forecast_origin: date | None = None
    model_uri: str | None = None
    limitation: str | None = None


class IntervalRequest(ForecastRequest):
    coverage: Literal[0.8, 0.95] = 0.8


class IntervalDay(BaseModel):
    date: date
    prediction: float
    lower: float
    upper: float


class IntervalResponse(BaseModel):
    product_id: int
    store_id: int
    method: str
    forecast_origin: date
    coverage: float
    calibration_count: int
    calibration_start: date
    calibration_end: date
    limitation: str
    forecasts: list[IntervalDay]


class ForecastMethod(BaseModel):
    id: Literal["hybrid", "tsb", "moving_average", "seasonal_naive"]
    label: str
    status: Literal["established", "experimental"]
    configuration: str
    limitation: str


class ForecastMethodsResponse(BaseModel):
    methods: list[ForecastMethod]
