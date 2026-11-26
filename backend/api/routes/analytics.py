
from fastapi import APIRouter, HTTPException, Path, Query

from backend.api.schemas.analytics import (
    OverviewResponse,
    ProductAnalyticsResponse,
    StoreAnalyticsResponse,
    TrendResponse,
    TrendDay,
)

from backend.services.analytics_service import (
    AnalyticsNotFoundError,
    get_product_summary,
    get_store_summary,
    get_product_store_trend,
    get_platform_overview,
    summarize_period,
)



router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get(
    "/products/{product_id}",
    response_model=ProductAnalyticsResponse,
)
def product_analytics(
    product_id: int = Path(gt=0),
    days: int = Query(default=90, ge=1, le=365),
):
    try:
        return get_product_summary(
            product_id=product_id,
            days=days,
        )

    except AnalyticsNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


@router.get(
    "/stores/{store_id}",
    response_model=StoreAnalyticsResponse,
)
def store_analytics(
    store_id: int = Path(gt=0),
    days: int = Query(default=90, ge=1, le=365),
):
    try:
        return get_store_summary(
            store_id=store_id,
            days=days,
        )

    except AnalyticsNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


@router.get(
    "/trends",
    response_model=TrendResponse,
)
def demand_trends(
    product_id: int = Query(gt=0),
    store_id: int = Query(gt=0),
    days: int = Query(default=90, ge=1, le=365),
):
    try:
        trend_df = get_product_store_trend(
            product_id=product_id,
            store_id=store_id,
            days=days,
        )

        trend = [
            TrendDay(
                date=row.date.date(),
                sales_quantity=int(row.sales_quantity),
            )
            for row in trend_df.itertuples(index=False)
        ]

        total_demand = int(trend_df["sales_quantity"].sum())
        period = summarize_period(
            trend_df["date"].max(), days, total_demand, len(trend_df),
            trend_df["sales_quantity"].gt(0).sum(),
        )

        return TrendResponse(
            product_id=product_id,
            store_id=store_id,
            days=days,
            total_demand=total_demand,
            **period,
            trend=trend,
        )

    except AnalyticsNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )



@router.get("/overview", response_model=OverviewResponse)
def platform_overview(
    days: int = Query(default=90, ge=1, le=365),
):
    try:
        return get_platform_overview(days=days)

    except AnalyticsNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
