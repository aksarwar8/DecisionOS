from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Pair(BaseModel):
    product_id: int = Field(gt=0, le=2**31 - 1)
    store_id: int = Field(gt=0, le=2**31 - 1)


class BatchRequest(BaseModel):
    scope: Literal["pair", "product", "pairs", "store", "state", "category", "department", "business"]
    product_ids: list[int] = Field(default_factory=list, max_length=100)
    store_ids: list[int] = Field(default_factory=list, max_length=100)
    pairs: list[Pair] = Field(default_factory=list, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    horizon: Literal[7, 14, 28] = 7
    origin: date | None = Field(default=None, ge=date(2, 1, 1))

    @model_validator(mode="after")
    def validate_scope(self):
        for values in (self.product_ids, self.store_ids):
            if len(values) != len(set(values)) or any(value < 1 or value > 2**31 - 1 for value in values):
                raise ValueError("Product and store selections must contain distinct positive IDs.")
        pairs = [(pair.product_id, pair.store_id) for pair in self.pairs]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Product-store pairs must be distinct.")
        if self.scope == "pairs":
            if not pairs or self.product_ids or self.store_ids:
                raise ValueError("Pair scope requires explicit pairs and no separate ID selections.")
        elif pairs:
            raise ValueError("Explicit pairs require pairs scope.")
        if self.scope == "pair" and (len(self.product_ids) != 1 or len(self.store_ids) != 1):
            raise ValueError("Pair scope requires one product and one store.")
        if self.scope == "product" and len(self.product_ids) != 1:
            raise ValueError("Product scope requires one product.")
        if self.scope == "store" and len(self.store_ids) != 1:
            raise ValueError("Store scope requires one store.")
        if self.scope in ("state", "category", "department") and not getattr(self, self.scope):
            raise ValueError(f"{self.scope.title()} scope requires its corresponding filter.")
        return self


class Exclusion(Pair):
    reason: str


class Preview(BaseModel):
    scope: BatchRequest
    candidate_pairs: int
    eligible_pairs: int | None
    excluded_pairs: int | None
    exclusions: list[Exclusion]
    estimated_rows: int
    max_pairs: int
    max_rows: int
    within_limits: bool


class Daily(BaseModel):
    date: date
    prediction: float


class HistoricalDay(BaseModel):
    date: date
    demand: float


class Breakdown(BaseModel):
    dimension: Literal["product", "store", "category", "department", "state"]
    id: int | str | None
    label: str
    prediction: float


class BatchResponse(Preview):
    origin: date
    forecast_start: date
    forecast_end: date
    model_uri: str
    model_version: str
    historical: list[HistoricalDay]
    daily: list[Daily]
    total_prediction: float
    breakdowns: list[Breakdown]
    coverage: Literal["complete", "partial"]
    extraction_seconds: float
    inference_seconds: float
