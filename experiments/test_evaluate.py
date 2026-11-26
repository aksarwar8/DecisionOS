if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.baseline import seasonal_naive_forecast
    from src.decisionos.ml.split import temporal_split
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # Step 1: Load 90 days of sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Split data chronologically
    train_df, validation_df, test_df = temporal_split(
        sales_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )

    print("Train period:", train_df["date"].min(), "to", train_df["date"].max())
    print("Validation period:", validation_df["date"].min(), "to", validation_df["date"].max())
    print("Test period:", test_df["date"].min(), "to", test_df["date"].max())


    # Step 3: Generate seasonal naive predictions
    forecast_df = seasonal_naive_forecast(
        sales_df,
        seasonal_period=7,
    )


    # Step 4: Keep only test-period predictions
    test_forecasts = forecast_df[
        forecast_df["date"] > "2011-04-14"
    ].copy()


    # Step 5: Evaluate forecasting performance
    metrics = evaluate_forecasts(
        actual=test_forecasts["sales_quantity"],
        predicted=test_forecasts["prediction"],
    )


    # Step 6: Display results
    print("\nBaseline Model Evaluation")
    print("----------------------")

    for metric, value in metrics.items():
        print(f"{metric}: {value}")
