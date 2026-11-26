
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)

    year: int
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    day_of_week: int = Field(ge=0, le=6)
    week_of_year: int = Field(ge=1, le=53)
    is_weekend: int = Field(ge=0, le=1)

    lag_7: float = Field(ge=0)
    lag_14: float = Field(ge=0)
    lag_28: float = Field(ge=0)

    rolling_mean_7: float = Field(ge=0)
    rolling_mean_28: float = Field(ge=0)
    rolling_std_7: float = Field(ge=0)


class PredictionResponse(BaseModel):
    product_id: int
    store_id: int
    prediction: float
