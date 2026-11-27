"""Bounded pair-level operational demand signals."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.decisionos.data.extract_forecast import extract_product_store_history
from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.monitoring.anomalies import detect_demand_anomalies

router = APIRouter(prefix="/risk", tags=["Operational risk"])


class Evidence(BaseModel):
    prior_days: int
    median: float
    mad: float
    modified_z: float | None
    zero_run_days: int | None


class Anomaly(BaseModel):
    date: date
    product_id: int | None
    store_id: int
    type: Literal["spike", "demand_drop", "prolonged_zero", "price_change"]
    severity: Literal["medium", "high"]
    risk_score: int
    observed: float
    reference: float
    evidence: Evidence


class RiskResponse(BaseModel):
    product_id: int | None
    store_id: int
    analysis_start: date
    analysis_end: date
    limitation: str
    anomalies: list[Anomaly]


@router.get("/demand", response_model=RiskResponse)
def demand_risk(product_id: int = Query(gt=0), store_id: int = Query(gt=0),
                severity: Literal["all", "medium", "high"] = "all"):
    try:
        history = extract_product_store_history(product_id, store_id, 90)
        anomalies = detect_demand_anomalies(history)
        if severity != "all":
            anomalies = [item for item in anomalies if item["severity"] == severity]
        return RiskResponse(product_id=product_id, store_id=store_id,
                            analysis_start=history.date.min().date(), analysis_end=history.date.max().date(),
                            limitation="Statistical historical signals are not evidence of stockouts or fraud.",
                            anomalies=anomalies)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/store", response_model=RiskResponse)
def store_risk(store_id: int = Query(gt=0), severity: Literal["all", "medium", "high"] = "all"):
    import pandas as pd

    from backend.api.routes.sales_intelligence import _execute
    from backend.api.schemas.sales_intelligence import SalesFilters
    from backend.services.sales_intelligence_service import get_sales_trend

    result = _execute(get_sales_trend, SalesFilters(store_id=store_id, days=90), "daily")
    trend = result["trend"]
    if not trend:
        raise HTTPException(status_code=404, detail="No sales observations found for this store.")
    history = pd.DataFrame(trend).rename(columns={"period": "date", "total_demand": "sales_quantity"})
    history = history.assign(product_id=0, store_id=store_id)
    try:
        anomalies = detect_demand_anomalies(history)
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    for anomaly in anomalies:
        anomaly["product_id"] = None
    if severity != "all":
        anomalies = [item for item in anomalies if item["severity"] == severity]
    return RiskResponse(product_id=None, store_id=store_id, analysis_start=result["period_start"],
                        analysis_end=result["period_end"],
                        limitation="Signals describe observed store totals and do not establish stockouts or fraud.",
                        anomalies=anomalies)


@router.get("/price", response_model=RiskResponse)
def price_risk(product_id: int = Query(gt=0), store_id: int = Query(gt=0),
               severity: Literal["all", "medium", "high"] = "all"):
    from backend.api.schemas.calendar_intelligence import PriceQuery
    from backend.api.routes.calendar_intelligence import _supported
    from backend.services.price_intelligence_service import get_price_intelligence

    result = _supported(get_price_intelligence, PriceQuery(product_id=product_id, store_id=store_id, days=90))
    anomalies = []
    for change in result["changes"]:
        previous = change["previous_price"]
        current = change["current_price"]
        if previous is None or current is None or previous <= 0:
            continue
        difference = (current - previous) / previous
        if abs(difference) >= 0.3:
            high = abs(difference) >= 0.6
            if severity != "all" and severity != ("high" if high else "medium"):
                continue
            anomalies.append({"date": change["week_start"], "product_id": product_id, "store_id": store_id,
                              "type": "price_change", "severity": "high" if high else "medium",
                              "risk_score": 80 if high else 50, "observed": current, "reference": previous,
                              "evidence": {"prior_days": 7, "median": previous, "mad": 0,
                                           "modified_z": None, "zero_run_days": None}})
    return RiskResponse(product_id=product_id, store_id=store_id, analysis_start=result["period_start"],
                        analysis_end=result["period_end"],
                        limitation="Weekly quoted-price changes are descriptive; currency is not specified.",
                        anomalies=anomalies)
