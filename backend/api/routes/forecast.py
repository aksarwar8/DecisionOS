from fastapi import APIRouter, HTTPException

from uuid import UUID

from backend.api.schemas.batch_forecast import BatchRequest, BatchResponse, ForecastRun, Preview
from backend.api.schemas.forecast import (
    ForecastDay, ForecastMethodsResponse, ForecastRequest, ForecastResponse, IntervalRequest, IntervalResponse,
)
from backend.services import batch_forecast_service
from backend.services.forecast_service import generate_product_forecast
from src.decisionos.data.validate import HistoricalSalesError

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.post("/scope-preview", response_model=Preview)
def preview_scope(request: BatchRequest):
    try:
        return batch_forecast_service.scope_preview(request)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/runs", response_model=ForecastRun)
def execute_forecast_run(request: BatchRequest):
    from backend.services.forecast_runs import execute_run
    try:
        return execute_run(request)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/runs", response_model=list[ForecastRun])
def list_forecast_runs():
    from backend.services.forecast_runs import list_runs
    return list_runs()


@router.get("/runs/{run_id}", response_model=ForecastRun)
def get_forecast_run(run_id: UUID):
    from backend.services.forecast_runs import get_run
    try:
        return get_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Forecast run not found.") from error


@router.post("/batch", response_model=BatchResponse)
def batch_forecast(request: BatchRequest):
    try:
        return batch_forecast_service.generate_batch(request)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/", response_model=ForecastResponse)
def create_forecast(request: ForecastRequest):
    from datetime import timedelta
    from src.decisionos.config import get_settings
    from src.decisionos.ml.strategies import METHODS
    try:
        forecast_df = generate_product_forecast(
            product_id=request.product_id, store_id=request.store_id, horizon=request.horizon,
            **({"method": request.method} if request.method != "hybrid" else {}),
        )
        forecasts = [ForecastDay(date=row.date.date(), demand_segment=row.demand_segment,
                                 selected_model=row.selected_model, prediction=float(row.prediction))
                     for row in forecast_df.itertuples(index=False)]
        return ForecastResponse(product_id=request.product_id, store_id=request.store_id, horizon=request.horizon,
                                total_predicted_demand=sum(item.prediction for item in forecasts), forecasts=forecasts,
                                method=request.method, forecast_origin=forecasts[0].date - timedelta(days=1),
                                model_uri=(get_settings().registered_model_uri if request.method == "hybrid"
                                           else f"builtin:{request.method}:v1"),
                                limitation=METHODS[request.method]["limitation"])
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/methods", response_model=ForecastMethodsResponse)
def available_methods():
    from src.decisionos.ml.strategies import METHODS
    return {"methods": [{"id": key, **value} for key, value in METHODS.items()]}


@router.post("/intervals", response_model=IntervalResponse)
def forecast_intervals(request: IntervalRequest):
    from backend.services.model_service import load_forecasting_model
    from src.decisionos.data.extract_forecast import extract_product_store_history
    from src.decisionos.ml.strategies import rolling_intervals

    try:
        history = extract_product_store_history(request.product_id, request.store_id, lookback_days=90)
        model = load_forecasting_model() if request.method == "hybrid" else None
        forecasts, count = rolling_intervals(history, request.horizon, request.method, request.coverage, model)
        history = history.sort_values("date")
        return IntervalResponse(
            product_id=request.product_id, store_id=request.store_id, method=request.method,
            forecast_origin=history.date.max().date(), coverage=request.coverage, calibration_count=count,
            calibration_start=history.date.iloc[28].date(), calibration_end=history.date.max().date(),
            limitation="Rolling residuals overlap in time; coverage under distribution shift is not guaranteed.",
            forecasts=forecasts,
        )
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
