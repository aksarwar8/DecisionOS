if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.split import temporal_split
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.predict import predict_demand


    # Step 1: Prepare data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )

    ml_df = prepare_ml_dataset(sales_df)


    # Step 2: Split chronologically
    train_df, validation_df, test_df = temporal_split(
        ml_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )


    # Step 3: Load saved model
    model = load_model(
        model_name="random_forest_v1.joblib",
    )


    # Step 4: Generate predictions
    predictions_df = predict_demand(
        model=model,
        input_df=test_df.head(20),
    )


    # Step 5: Inspect output
    print("\nPrediction output:")
    print(
        predictions_df[
            [
                "product_id",
                "store_id",
                "date",
                "sales_quantity",
                "prediction",
            ]
        ].to_string(index=False)
    )

    print("\nNegative predictions:", (predictions_df["prediction"] < 0).sum())
    print("Prediction rows:", len(predictions_df))
