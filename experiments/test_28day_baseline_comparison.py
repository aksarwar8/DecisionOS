if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.forecast import recursive_forecast
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # Step 1: Load historical data
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
        start="2011-04-01",
        end="2011-04-28",
        freq="D",
    )


    # Step 2: Prepare future product-store combinations
    combinations = history_df[
        ["product_id", "store_id"]
    ].drop_duplicates()

    future_targets = combinations.merge(
        pd.DataFrame({"date": future_dates}),
        how="cross",
    )


    # Step 3: Historical Mean baseline
    historical_means = (
        history_df.groupby(
            ["product_id", "store_id"]
        )["sales_quantity"]
        .mean()
        .reset_index(name="prediction")
    )

    mean_forecasts = future_targets.merge(
        historical_means,
        on=["product_id", "store_id"],
        how="left",
    )


    # Step 4: Seasonal Naive baseline
    seasonal_history = history_df.sort_values(
        ["product_id", "store_id", "date"]
    )

    seasonal_series = {
        key: group["sales_quantity"].astype(float).tolist()
        for key, group in seasonal_history.groupby(
            ["product_id", "store_id"]
        )
    }

    seasonal_rows = []

    for forecast_date in future_dates:
        daily_rows = []

        for key, values in seasonal_series.items():
            prediction = values[-7]

            daily_rows.append({
                "product_id": key[0],
                "store_id": key[1],
                "date": forecast_date,
                "prediction": prediction,
            })

        seasonal_rows.extend(daily_rows)

        # Feed seasonal predictions into the next forecast day.
        for key, prediction in zip(
            seasonal_series.keys(),
            [row["prediction"] for row in daily_rows],
        ):
            seasonal_series[key].append(prediction)

    seasonal_forecasts = pd.DataFrame(seasonal_rows)


    # Step 5: Random Forest recursive forecasts
    model = load_model("random_forest_v1.joblib")

    rf_forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 6: Actual future demand
    actual = actual_future[
        ["product_id", "store_id", "date", "sales_quantity"]
    ]


    # Step 7: Evaluate all three models
    models = {
        "Historical Mean": mean_forecasts,
        "Seasonal Naive": seasonal_forecasts,
        "Random Forest": rf_forecasts,
    }

    print("\n28-DAY FORECAST COMPARISON")
    print("=" * 55)

    for name, forecasts in models.items():

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

        print(f"\n{name}")
        print("-" * 35)

        for metric, value in metrics.items():
            print(f"{metric}: {value}")

        print(
            "Total predicted demand:",
            evaluation["prediction"].sum(),
        )
