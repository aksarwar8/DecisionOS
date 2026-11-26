if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.split import temporal_split
    from src.decisionos.ml.train import train_random_forest
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # Step 1: Extract sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Prepare ML dataset
    ml_df = prepare_ml_dataset(sales_df)


    # Step 3: Chronological split
    train_df, validation_df, test_df = temporal_split(
        ml_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )


    print("\nDataset split")
    print("-" * 30)
    print("Train rows:", len(train_df))
    print("Validation rows:", len(validation_df))
    print("Test rows:", len(test_df))


    # Step 4: Train Random Forest
    model = train_random_forest(
        train_df=train_df,
        n_estimators=100,
    )


    # Step 5: Generate predictions on test data
    from src.decisionos.ml.train import FEATURE_COLUMNS

    X_test = test_df[FEATURE_COLUMNS]

    predictions = model.predict(X_test)


    # Step 6: Evaluate model
    metrics = evaluate_forecasts(
        actual=test_df["sales_quantity"],
        predicted=predictions,
    )


    print("\nRandom Forest Evaluation")
    print("-" * 30)

    for metric, value in metrics.items():
        print(f"{metric}: {value}")


    # Step 7: Feature importance
    import pandas as pd

    importance_df = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": model.feature_importances_,
    })

    importance_df = importance_df.sort_values(
        "importance",
        ascending=False,
    )

    print("\nFeature Importance")
    print("-" * 30)
    print(importance_df.to_string(index=False))
