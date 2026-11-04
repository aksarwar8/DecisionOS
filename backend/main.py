
from fastapi import FastAPI
from backend.routes import forecast_routes
from backend.routes import model_routes

app = FastAPI(
    title="DecisionOS API",
    description="Demand Forecasting and Decision Intelligence Platform",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Welcome to DecisionOS API",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


app.include_router(model_routes.router)


app.include_router(forecast_routes.router)

from backend.routes import product_routes

app.include_router(product_routes.router)

from backend.routes import sales_routes

app.include_router(sales_routes.router)