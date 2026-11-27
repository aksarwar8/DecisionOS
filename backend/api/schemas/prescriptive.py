"""Typed simulated inventory inputs and decision outputs."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Assumptions(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    stock: float = Field(default=20, ge=0, le=1_000_000)
    incoming: float = Field(default=0, ge=0, le=1_000_000)
    lead_days: int = Field(default=7, ge=1, le=21)
    safety_stock: float = Field(default=10, ge=0, le=1_000_000)
    minimum_order: int = Field(default=1, ge=1, le=1_000_000)
    order_multiple: int = Field(default=1, ge=1, le=1_000_000)
    service_level: float = Field(default=0.95, ge=0.5, le=0.999)
    unit_cost: float = Field(default=1, ge=0, le=100_000)
    holding_cost: float = Field(default=0.01, ge=0, le=100_000)
    shortage_cost: float = Field(default=2, ge=0, le=100_000)
    fixed_order: int = Field(default=25, ge=1, le=1_000_000)
    simulation_budget: float = Field(default=500, ge=0, le=100_000_000)


class InventoryRecord(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    assumptions: Assumptions
    label: Literal["simulated"] = "simulated"


class DecisionRequest(BaseModel):
    run_id: UUID
    assumptions: Assumptions = Field(default_factory=Assumptions)


class ProjectionDay(BaseModel):
    date: date
    day: int
    demand: float
    stock: float
    unfulfilled: float


class DecisionResponse(BaseModel):
    product_id: int
    store_id: int
    run_id: UUID
    forecast_origin: date
    model_uri: str
    model_version: str
    method: str
    assumptions: Assumptions
    inventory_position: float
    lead_time_demand: float
    reorder_point: float
    order_up_to: float
    recommended_quantity: int
    estimated_procurement_cost: float
    projected_shortage: float
    projected_ending_stock: float
    shortage_exposure: float
    holding_exposure: float
    stockout_indicator: bool
    overstock_indicator: bool
    estimated_fill_rate: float | None
    coverage_days: float | None
    priority: Literal["high", "medium", "low"]
    projection: list[ProjectionDay]
    explanation: str
    limitation: str


class BudgetRequest(BaseModel):
    items: list[DecisionRequest] = Field(min_length=1, max_length=20)
    budget: float = Field(ge=0, le=100_000_000, allow_inf_nan=False)


class Allocation(BaseModel):
    product_id: int
    store_id: int
    quantity: int
    cost: float


class BudgetResponse(BaseModel):
    allocations: list[Allocation]
    spent: float
    remaining: float
    method: str


class ScenarioRequest(DecisionRequest):
    demand_multiplier: float = Field(default=1, ge=0, le=5, allow_inf_nan=False)
    stock_multiplier: float = Field(default=1, ge=0, le=5, allow_inf_nan=False)
    lead_days_delta: int = Field(default=0, ge=-20, le=20)
    unit_cost_multiplier: float = Field(default=1, ge=0, le=5, allow_inf_nan=False)
    holding_cost_multiplier: float = Field(default=1, ge=0, le=5, allow_inf_nan=False)
    service_level: float | None = Field(default=None, ge=0.5, le=0.999)
    budget: float | None = Field(default=None, ge=0, le=100_000_000, allow_inf_nan=False)


class ScenarioResponse(BaseModel):
    baseline: DecisionResponse
    scenario: DecisionResponse
    budget_allocation: BudgetResponse | None = None
    notice: str


class SimulationRequest(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    assumptions: Assumptions = Field(default_factory=Assumptions)


class SimulationDay(BaseModel):
    date: date
    stock: float
    demand: float
    unfulfilled: float
    order: float
    forecast_daily: float


class SimulationResult(BaseModel):
    policy: str
    fill_rate: float | None
    stockout_days: int
    unfulfilled_demand: float
    average_inventory: float
    replenishment_quantity: float
    holding_cost: float
    shortage_cost: float
    procurement_cost: float
    total_relevant_cost: float
    trace: list[SimulationDay]


class SimulationResponse(BaseModel):
    product_id: int
    store_id: int
    start: date
    end: date
    assumptions: Assumptions
    policies: list[SimulationResult]
    limitation: str


class ReviewRequest(BaseModel):
    decision: DecisionResponse
    status: Literal["review", "approved", "rejected"]


class ReviewResponse(ReviewRequest):
    id: UUID
    created_at: datetime
