if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.forecast import recursive_forecast
    from src.decisionos.ml.hybrid import hybrid_forecast
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # Step 1: Load historical and actual test data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )

    history_df = sales_df[
        sales_df["date"] <= "2011-03-31"
    ].copy()

    actual_future = sales_df[
        sales_df["date"] > "2011-03-31"
    ].copy()

    future_dates = pd.date_range(
        "2011-04-01",
        "2011-04-28",
        freq="D",
    )


    # Step 2: Load the trained hybrid Random Forest
    model = load_model(
        "random_forest_hybrid_v1.joblib"
    )


    # Step 3: Generate Random Forest forecasts
    rf_forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 4: Generate Historical Mean forecasts
    historical_means = (
        history_df.groupby(
            ["product_id", "store_id"]
        )["sales_quantity"]
        .mean()
        .reset_index(name="prediction")
    )

    mean_forecasts = rf_forecasts[
        ["product_id", "store_id", "date"]
    ].merge(
        historical_means,
        on=["product_id", "store_id"],
    )


    # Step 5: Generate Seasonal Naive forecasts
    seasonal_series = {
        key: group.sort_values("date")["sales_quantity"]
        .astype(float).tolist()
        for key, group in history_df.groupby(
            ["product_id", "store_id"]
        )
    }

    seasonal_rows = []

    for forecast_date in future_dates:

        daily_predictions = {}

        for key, values in seasonal_series.items():
            daily_predictions[key] = values[-7]

            seasonal_rows.append({
                "product_id": key[0],
                "store_id": key[1],
                "date": forecast_date,
                "prediction": values[-7],
            })

        for key, prediction in daily_predictions.items():
            seasonal_series[key].append(prediction)

    seasonal_forecasts = pd.DataFrame(seasonal_rows)


    # Step 6: Generate Hybrid forecasts
    hybrid_df = hybrid_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )

    hybrid_predictions = hybrid_df[
        ["product_id", "store_id", "date", "prediction"]
    ]


    # Step 7: Prepare actual test data
    actual = actual_future[
        ["product_id", "store_id", "date", "sales_quantity"]
    ]


    # Step 8: Evaluate all four approaches
    models = {
        "Historical Mean": mean_forecasts,
        "Seasonal Naive": seasonal_forecasts,
        "Random Forest": rf_forecasts,
        "Hybrid": hybrid_predictions,
    }

    results = []

    for model_name, forecasts in models.items():

        evaluation = forecasts.merge(
            actual,
            on=["product_id", "store_id", "date"],
            how="inner",
            validate="one_to_one",
        )

        metrics = evaluate_forecasts(
            actual=evaluation["sales_quantity"],
            predicted=evaluation["prediction"],
        )

        results.append({
            "Model": model_name,
            **metrics,
            "Total Predicted Demand": evaluation["prediction"].sum(),
        })


    # Step 9: Display comparison
    results_df = pd.DataFrame(results)

    print("\nFINAL 28-DAY MODEL COMPARISON")
    print("=" * 75)

    print(
        results_df.to_string(
            index=False,
            formatters={
                "MAE": "{:.4f}".format,
                "RMSE": "{:.4f}".format,
                "WAPE": "{:.2f}%".format,
                "Total Predicted Demand": "{:,.2f}".format,
            },
        )
    )

    print(
        "\nActual total demand:",
        actual["sales_quantity"].sum(),
    )
