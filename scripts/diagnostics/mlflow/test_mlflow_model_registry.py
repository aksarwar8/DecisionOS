if __name__ == "__main__":

    from src.decisionos.config import get_settings

    import mlflow
    from mlflow.tracking import MlflowClient


    settings = get_settings()
    TRACKING_URI = settings.resolve_tracking_uri()

    LOGGED_MODEL_ID = "m-55e18b6774e04082b4789e3d30a5976a"

    REGISTERED_MODEL_NAME = settings.model_name


    mlflow.set_tracking_uri(TRACKING_URI)

    client = MlflowClient(tracking_uri=TRACKING_URI)


    # Register the existing logged model.
    print("\nREGISTERING DECISIONOS MODEL")
    print("=" * 55)

    registered_model = mlflow.register_model(
        model_uri=f"models:/{LOGGED_MODEL_ID}",
        name=REGISTERED_MODEL_NAME,
    )

    print("Registered model:", registered_model.name)
    print("Model version:", registered_model.version)


    # Add model description.
    client.update_registered_model(
        name=REGISTERED_MODEL_NAME,
        description=(
            "DecisionOS hybrid demand forecasting model. "
            "Uses Random Forest for low, medium and high demand "
            "segments, and Historical Mean for zero-average demand."
        ),
    )


    # Assign a candidate alias.
    client.set_registered_model_alias(
        name=REGISTERED_MODEL_NAME,
        alias=settings.model_alias,
        version=registered_model.version,
    )


    # Verify registration.
    model_version = client.get_model_version(
        name=REGISTERED_MODEL_NAME,
        version=registered_model.version,
    )

    print("\nREGISTRATION VERIFIED")
    print("-" * 55)

    print("Model name:", model_version.name)
    print("Version:", model_version.version)
    print("Status:", model_version.status)
    print("Source:", model_version.source)
    print("Run ID:", model_version.run_id)

    print("\nCandidate alias assigned successfully.")
