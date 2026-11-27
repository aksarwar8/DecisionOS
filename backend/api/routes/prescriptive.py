"""Simulated inventory analysis and decisions."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from backend.api.schemas.prescriptive import (
    Assumptions, BudgetRequest, BudgetResponse, DecisionRequest, DecisionResponse, InventoryRecord,
    ReviewRequest, ReviewResponse, ScenarioRequest, ScenarioResponse, SimulationRequest, SimulationResponse,
)
from backend.services import prescriptive_service as service
from src.decisionos.data.extract_forecast import extract_product_store_history
from src.decisionos.data.validate import HistoricalSalesError
from src.decisionos.inventory.simulation import simulate
from src.decisionos.inventory.decisions import allocate

router = APIRouter(prefix="/prescriptive", tags=["Simulated inventory"])


def _decision(request):
    try:
        return service.make_decision(request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Forecast run not found.") from error
    except (ValueError, HistoricalSalesError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/assumptions", response_model=Assumptions)
def assumptions(product_id: int = Query(gt=0), store_id: int = Query(gt=0), seed: int = 42):
    return service.synthetic_assumptions(product_id, store_id, seed)


@router.put("/inventory/{product_id}/{store_id}", response_model=InventoryRecord)
def save_inventory(product_id: int, store_id: int, assumptions: Assumptions):
    if product_id <= 0 or store_id <= 0:
        raise HTTPException(status_code=422, detail="Product and store IDs must be positive.")
    return service.save_inventory(product_id, store_id, assumptions)


@router.get("/inventory/{product_id}/{store_id}", response_model=InventoryRecord)
def load_inventory(product_id: int, store_id: int):
    if product_id <= 0 or store_id <= 0:
        raise HTTPException(status_code=422, detail="Product and store IDs must be positive.")
    try:
        return service.load_inventory(product_id, store_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Simulated inventory record not found.") from error


@router.post("/recommendation", response_model=DecisionResponse)
def recommendation(request: DecisionRequest):
    return _decision(request)


@router.post("/allocation", response_model=BudgetResponse)
def allocation(request: BudgetRequest):
    try:
        return service.budget_allocation(request.items, request.budget)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Forecast run not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/scenario", response_model=ScenarioResponse)
def scenario(request: ScenarioRequest):
    base = _decision(DecisionRequest(run_id=request.run_id, assumptions=request.assumptions))
    values = request.assumptions.model_dump()
    values["stock"] *= request.stock_multiplier
    values["lead_days"] += request.lead_days_delta
    values["unit_cost"] *= request.unit_cost_multiplier
    values["holding_cost"] *= request.holding_cost_multiplier
    if request.service_level is not None:
        values["service_level"] = request.service_level
    try:
        modified = DecisionRequest(run_id=request.run_id, assumptions=Assumptions.model_validate(values))
        result = service.make_decision(modified, request.demand_multiplier)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Scenario parameters exceed supported limits.") from error
    allocation_result = None
    if request.budget is not None:
        allocation_result = allocate([{"product_id": result.product_id, "store_id": result.store_id,
                                       "quantity": result.recommended_quantity, "priority_score": 0,
                                       "unit_cost": result.assumptions.unit_cost,
                                       "minimum_order": result.assumptions.minimum_order,
                                       "order_multiple": result.assumptions.order_multiple}], request.budget)
        result = service.make_decision(modified, request.demand_multiplier,
                                       order_override=allocation_result["allocations"][0]["quantity"])
    return ScenarioResponse(
        baseline=base, scenario=result, budget_allocation=allocation_result,
        notice="Simulated point-demand scenarios; service level does not set safety stock.",
    )


@router.post("/simulation", response_model=SimulationResponse)
def simulation(request: SimulationRequest):
    try:
        data = extract_product_store_history(request.product_id, request.store_id, 90)
        policies = [simulate(data, request.assumptions.model_dump(), name)
                    for name in ("none", "fixed", "reorder", "forecast", "budget")]
        return SimulationResponse(product_id=request.product_id, store_id=request.store_id,
                                  start=data.sort_values("date").date.iloc[28].date(), end=data.date.max().date(),
                                  assumptions=request.assumptions, policies=policies,
                                  limitation="Observed historical sales proxy demand; all inventory and costs are simulated.")
    except (HistoricalSalesError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/reviews", response_model=ReviewResponse)
def save_review(request: ReviewRequest):
    return service.save_review(request)


@router.get("/reviews", response_model=list[ReviewResponse])
def reviews():
    return service.list_reviews()
