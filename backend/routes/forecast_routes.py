
from fastapi import APIRouter

from backend.schemas.forecast_schema import (
    ForecastRequest,
    ForecastResponse
)

from backend.services.forecast_service import predict_demand


router = APIRouter(
    prefix="/forecast",
    tags=["Demand Forecasting"]
)


@router.post("/predict", response_model=ForecastResponse)
def predict(request: ForecastRequest):

    prediction = predict_demand(request)

    return ForecastResponse(
        item_id=request.item_id,
        store_id=request.store_id,
        predicted_demand=max(0, prediction)
    )
