if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.forecast import recursive_forecast
    from src.decisionos.ml.evaluate import evaluate_forecasts
    import pandas as pd


    # Step 1: Load historical and evaluation data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Separate historical data from actual future sales
    history_df = sales_df[
        sales_df["date"] <= "2011-03-31"
    ].copy()

    actual_future = sales_df[
        sales_df["date"] > "2011-03-31"
    ].copy()


    # Step 3: Generate future dates
    future_dates = pd.date_range(
        start="2011-04-01",
        end="2011-04-28",
        freq="D",
    )


    # Step 4: Load trained model
    model = load_model(
        model_name="random_forest_v1.joblib",
    )


    # Step 5: Generate recursive forecasts
    forecast_df = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 6: Match predictions with actual sales
    evaluation_df = forecast_df.merge(
        actual_future[
            ["product_id", "store_id", "date", "sales_quantity"]
        ],
        on=["product_id", "store_id", "date"],
        how="inner",
        validate="one_to_one",
    )


    # Step 7: Evaluate the complete 28-day horizon
    print("\n28-DAY RECURSIVE FORECAST")
    print("=" * 45)

    metrics_28 = evaluate_forecasts(
        actual=evaluation_df["sales_quantity"],
        predicted=evaluation_df["prediction"],
    )

    for metric, value in metrics_28.items():
        print(f"{metric}: {value}")


    # Step 8: Evaluate the first 14 days
    first_14 = evaluation_df[
        evaluation_df["date"] <= "2011-04-14"
    ]

    metrics_14 = evaluate_forecasts(
        actual=first_14["sales_quantity"],
        predicted=first_14["prediction"],
    )

    print("\nFIRST 14 DAYS")
    print("=" * 45)

    for metric, value in metrics_14.items():
        print(f"{metric}: {value}")


    # Step 9: Evaluate the second 14 days
    second_14 = evaluation_df[
        evaluation_df["date"] > "2011-04-14"
    ]

    metrics_second_14 = evaluate_forecasts(
        actual=second_14["sales_quantity"],
        predicted=second_14["prediction"],
    )

    print("\nDAYS 15–28")
    print("=" * 45)

    for metric, value in metrics_second_14.items():
        print(f"{metric}: {value}")
