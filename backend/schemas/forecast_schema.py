
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    item_id: str
    store_id: str

    lag_1: float = Field(ge=0)
    lag_7: float = Field(ge=0)
    lag_14: float = Field(ge=0)
    rolling_mean_7: float = Field(ge=0)

    weekday: int = Field(ge=0, le=6)
    month: int = Field(ge=1, le=12)


class ForecastResponse(BaseModel):
    item_id: str
    store_id: str
    predicted_demand: float
