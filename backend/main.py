
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.routes import (
    health,
    model,
    prediction,
    forecast,
    analytics,
    catalog,
    sales_intelligence,
    product_intelligence,
)
from src.decisionos.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield


app = FastAPI(
    title="DecisionOS API",
    description=(
        "Demand forecasting and decision intelligence API."
    ),
    version="1.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.debug(
        "API response request_id=%s method=%s status=%s",
        request.state.request_id,
        request.method,
        response.status_code,
    )
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.exception(
        "Unhandled API error request_id=%s method=%s",
        request_id,
        request.method,
        exc_info=error,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred.", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


app.include_router(health.router)
app.include_router(model.router)
app.include_router(prediction.router)
app.include_router(forecast.router)


@app.get("/")
def root():
    return {
        "application": "DecisionOS",
        "message": "DecisionOS API is running.",
        "documentation": "/docs",
    }




app.include_router(analytics.router)
app.include_router(catalog.router)
app.include_router(sales_intelligence.router)
app.include_router(product_intelligence.router)
