from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.api.routes.sales_intelligence import _execute
from backend.api.schemas.calendar_intelligence import (
    CapabilitiesResponse, EventAnalysisResponse, EventCatalogResponse, EventQuery, EventWindowQuery,
    EventWindowResponse, PriceQuery, PriceResponse, SeasonalityQuery, SeasonalityResponse, SnapQuery,
    SnapResponse,
)
from backend.services import calendar_intelligence_service as service
from backend.services.price_intelligence_service import get_price_intelligence

router = APIRouter(prefix="/analytics", tags=["Seasonality and Events"])


def _supported(operation, *args):
    try:
        return _execute(operation, *args)
    except service.UnsupportedAnalyticsError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities():
    return service.get_capabilities()


@router.get("/seasonality", response_model=SeasonalityResponse)
def seasonality(query: Annotated[SeasonalityQuery, Query()]):
    return _execute(service.get_seasonality, query)


@router.get("/event-catalog", response_model=EventCatalogResponse)
def event_catalog():
    return _supported(service.get_event_catalog)


@router.get("/event-analysis", response_model=EventAnalysisResponse)
def event_analysis(query: Annotated[EventQuery, Query()]):
    return _supported(service.get_event_analysis, query)


@router.get("/event-window", response_model=EventWindowResponse)
def event_window(query: Annotated[EventWindowQuery, Query()]):
    return _supported(service.get_event_window, query)


@router.get("/snap-analysis", response_model=SnapResponse)
def snap_analysis(query: Annotated[SnapQuery, Query()]):
    return _supported(service.get_snap_analysis, query)


@router.get("/price-intelligence", response_model=PriceResponse)
def price_intelligence(query: Annotated[PriceQuery, Query()]):
    return _supported(get_price_intelligence, query)
