
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from backend.services.operational_metrics import snapshot
from src.decisionos.data.extract import get_engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "DecisionOS",
    }


@router.get("/health/ready")
def readiness_check():
    """Check database connectivity; MLflow and model loading are not checked."""
    engine = None
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database readiness check failed.") from error
    finally:
        if engine is not None:
            engine.dispose()
    return {"status": "ready", "database": "reachable", "model": "not_checked"}


@router.get("/metrics")
def operational_metrics():
    return snapshot()
