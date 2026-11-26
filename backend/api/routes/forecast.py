
from fastapi import APIRouter, HTTPException

from backend.api.schemas.forecast import (
    ForecastRequest,
    ForecastResponse,
    ForecastDay,
)

from backend.services.forecast_service import (
    generate_product_forecast,
)
from src.decisionos.data.validate import HistoricalSalesError
from backend.api.schemas.batch_forecast import BatchRequest, BatchResponse, Preview
from backend.services import batch_forecast_service


router = APIRouter(
    prefix="/forecast",
    tags=["Forecasting"],
)


@router.post("/scope-preview", response_model=Preview)
def preview_scope(request: BatchRequest):
    try:
        return batch_forecast_service.scope_preview(request)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/batch", response_model=BatchResponse)
def batch_forecast(request: BatchRequest):
    try:
        return batch_forecast_service.generate_batch(request)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/", response_model=ForecastResponse)
def create_forecast(request: ForecastRequest):

    try:
        forecast_df = generate_product_forecast(
            product_id=request.product_id,
            store_id=request.store_id,
            horizon=request.horizon,
        )

        forecasts = [
            ForecastDay(
                date=row.date.date(),
                demand_segment=row.demand_segment,
                selected_model=row.selected_model,
                prediction=float(row.prediction),
            )
            for row in forecast_df.itertuples(index=False)
        ]

        total_demand = sum(
            item.prediction for item in forecasts
        )

        return ForecastResponse(
            product_id=request.product_id,
            store_id=request.store_id,
            horizon=request.horizon,
            total_predicted_demand=total_demand,
            forecasts=forecasts,
        )

    except HistoricalSalesError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
