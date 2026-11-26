if __name__ == "__main__":

    import pandas as pd

    from backend.services.model_service import (
        load_forecasting_model,
        predict_demand,
    )

    from src.decisionos.ml.train import FEATURE_COLUMNS


    # Load registered model.
    model = load_forecasting_model()

    # Prepare sample input.
    sample = pd.DataFrame(
        [
            {
                "product_id": 1,
                "store_id": 1,
                "year": 2011,
                "month": 4,
                "day": 1,
                "day_of_week": 4,
                "week_of_year": 13,
                "is_weekend": 0,
                "lag_7": 2.0,
                "lag_14": 1.0,
                "lag_28": 2.0,
                "rolling_mean_7": 1.5,
                "rolling_mean_28": 1.8,
                "rolling_std_7": 0.7,
            }
        ],
        columns=FEATURE_COLUMNS,
    )

    # Generate prediction.
    predictions = predict_demand(
        model=model,
        input_df=sample,
    )

    print("\nMODEL SERVICE TEST")
    print("-" * 50)

    print("Input shape:", sample.shape)
    print("Prediction:", predictions[0])
    print("Prediction count:", len(predictions))

    print("\nModel service test completed.")
