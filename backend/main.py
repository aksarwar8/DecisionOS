
import logging
import time
import secrets
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import (
    health,
    model,
    prediction,
    forecast,
    analytics,
    catalog,
    sales_intelligence,
    product_intelligence,
    store_intelligence,
    calendar_intelligence,
    risk,
    prescriptive,
    monitoring,
)
from src.decisionos.logging_config import configure_logging
from backend.services.operational_metrics import record_request
from src.decisionos.config import get_settings

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

origins = [origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()]
if "*" in origins:
    raise ValueError("CORS origins must be explicit.")
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Request-ID"])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = uuid4().hex
    started = time.perf_counter()
    settings = get_settings()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token = settings.api_admin_token
        if not token and settings.app_env.lower() != "local":
            record_request(503, time.perf_counter() - started)
            return JSONResponse(status_code=503, content={"detail": "Mutation access is not configured."},
                                headers={"X-Request-ID": request.state.request_id})
        if token:
            authorization = request.headers.get("authorization", "")
            if not secrets.compare_digest(authorization, f"Bearer {token}"):
                record_request(401, time.perf_counter() - started)
                return JSONResponse(status_code=401, content={"detail": "Authentication required."},
                                    headers={"X-Request-ID": request.state.request_id})
    try:
        response = await call_next(request)
    except Exception:
        record_request(500, time.perf_counter() - started)
        raise
    record_request(response.status_code, time.perf_counter() - started)
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
app.include_router(store_intelligence.router)
app.include_router(calendar_intelligence.router)
app.include_router(risk.router)
app.include_router(prescriptive.router)
app.include_router(monitoring.router)
