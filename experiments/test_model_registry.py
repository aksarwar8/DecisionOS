if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.split import temporal_split
    from src.decisionos.ml.train import train_random_forest
    from src.decisionos.ml.registry import save_model, load_model
    from src.decisionos.ml.train import FEATURE_COLUMNS


    # Step 1: Prepare dataset
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )

    ml_df = prepare_ml_dataset(sales_df)


    # Step 2: Chronological split
    train_df, validation_df, test_df = temporal_split(
        ml_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )


    # Step 3: Train model
    model = train_random_forest(
        train_df=train_df,
        n_estimators=100,
    )


    # Step 4: Save model
    save_model(
        model,
        model_name="random_forest_v1.joblib",
    )


    # Step 5: Load model
    loaded_model = load_model(
        model_name="random_forest_v1.joblib",
    )


    # Step 6: Verify predictions
    original_predictions = model.predict(
        test_df[FEATURE_COLUMNS].head(10)
    )

    loaded_predictions = loaded_model.predict(
        test_df[FEATURE_COLUMNS].head(10)
    )


    print("\nOriginal predictions:")
    print(original_predictions)

    print("\nLoaded model predictions:")
    print(loaded_predictions)

    print(
        "\nPredictions identical:",
        (original_predictions == loaded_predictions).all(),
    )
