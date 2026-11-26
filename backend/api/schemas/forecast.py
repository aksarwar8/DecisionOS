
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    horizon: Literal[7, 14, 28] = 7


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
