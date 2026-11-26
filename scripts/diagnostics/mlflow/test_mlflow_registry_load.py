if __name__ == "__main__":

    from src.decisionos.config import get_settings

    import mlflow
    import pandas as pd

    from src.decisionos.ml.train import FEATURE_COLUMNS


    settings = get_settings()
    TRACKING_URI = settings.resolve_tracking_uri()

    MODEL_URI = (
        settings.registered_model_uri
    )

    mlflow.set_tracking_uri(TRACKING_URI)

    print("\nLOADING REGISTERED DECISIONOS MODEL")
    print("=" * 55)

    # Load the model using its registered candidate alias.
    model = mlflow.sklearn.load_model(MODEL_URI)

    print("Model loaded successfully.")
    print("Registry URI:", MODEL_URI)

    # Create one sample with the exact training feature schema.
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

    # Generate a prediction.
    prediction = model.predict(sample)

    print("\nREGISTRY PREDICTION TEST")
    print("-" * 55)

    print("Input features:", sample.shape)
    print("Prediction:", float(prediction[0]))

    print("\nRegistered model loading and prediction successful.")
