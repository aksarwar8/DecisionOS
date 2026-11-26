if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.split import temporal_split
    from src.decisionos.ml.baseline import (
        seasonal_naive_forecast,
        mean_baseline_forecast,
    )
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # Step 1: Load sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Chronological split
    train_df, validation_df, test_df = temporal_split(
        sales_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )


    # Step 3: Seasonal naive predictions
    seasonal_predictions = seasonal_naive_forecast(
        sales_df,
        seasonal_period=7,
    )

    seasonal_test = seasonal_predictions[
        seasonal_predictions["date"] > "2011-04-14"
    ].copy()


    # Step 4: Mean baseline predictions
    mean_test = mean_baseline_forecast(
        train_df=train_df,
        target_df=test_df,
    )


    # Step 5: Evaluate both models
    seasonal_metrics = evaluate_forecasts(
        actual=seasonal_test["sales_quantity"],
        predicted=seasonal_test["prediction"],
    )

    mean_metrics = evaluate_forecasts(
        actual=mean_test["sales_quantity"],
        predicted=mean_test["prediction"],
    )


    # Step 6: Display comparison
    comparison = {
        "Seasonal Naive": seasonal_metrics,
        "Mean Baseline": mean_metrics,
    }

    print("\nBASELINE MODEL COMPARISON")
    print("=" * 50)

    for model_name, metrics in comparison.items():
        print(f"\n{model_name}")
        print("-" * 30)

        for metric, value in metrics.items():
            print(f"{metric}: {value}")
