
import pandas as pd

from fastapi import APIRouter, HTTPException

from backend.api.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
)

from backend.services.model_service import (
    PredictionInputError,
    load_forecasting_model,
    predict_demand,
)

router = APIRouter(
    prefix="/predict",
    tags=["Prediction"],
)


@router.post("/", response_model=PredictionResponse)
def predict(request: PredictionRequest):

    try:
        input_df = pd.DataFrame(
            [request.model_dump()]
        )

        model = load_forecasting_model()

        predictions = predict_demand(
            model=model,
            input_df=input_df,
        )

        return PredictionResponse(
            product_id=request.product_id,
            store_id=request.store_id,
            prediction=float(predictions[0]),
        )

    except PredictionInputError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
