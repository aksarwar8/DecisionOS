"""Explicit, bounded historical diagnostics, not continuous monitoring."""
from fastapi import APIRouter, HTTPException, Query

from src.decisionos.data.extract_forecast import extract_product_store_history
from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.monitoring.drift import distribution_drift

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/demand-drift")
def demand_drift(product_id: int = Query(gt=0), store_id: int = Query(gt=0),
                 psi_threshold: float = Query(default=0.2, gt=0, le=10)):
    try:
        history = extract_product_store_history(product_id, store_id, lookback_days=90).sort_values("date")
    except HistoricalSalesError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    split = len(history) // 2
    reference, recent = history.iloc[:split], history.iloc[split:]
    result = distribution_drift(reference.sales_quantity, recent.sales_quantity)
    return {"product_id": product_id, "store_id": store_id, "mode": "historical replay",
            "reference_start": reference.date.min(), "reference_end": reference.date.max(),
            "recent_start": recent.date.min(), "recent_end": recent.date.max(),
            "diagnostic": result, "psi_threshold": psi_threshold,
            "alert": result["psi"] is not None and result["psi"] >= psi_threshold,
            "limitation": "Descriptive drift is not proof of forecast degradation."}
