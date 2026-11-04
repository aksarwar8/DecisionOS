
from fastapi import APIRouter, HTTPException

from backend.services.model_service import load_model

router = APIRouter(
    prefix="/model",
    tags=["Machine Learning Model"]
)


@router.get("/status")
def model_status():

    try:
        model = load_model()

        return {
            "model": "Product-Store LightGBM",
            "status": "loaded",
            "model_type": type(model).__name__
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
