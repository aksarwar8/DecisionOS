if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.forecast import recursive_forecast


    # Step 1: Load sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Separate historical and future data
    history_df = sales_df[
        sales_df["date"] <= "2011-03-31"
    ].copy()

    actual_future = sales_df[
        sales_df["date"] > "2011-03-31"
    ].copy()


    # Step 3: Generate 28-day forecasts
    future_dates = pd.date_range(
        start="2011-04-01",
        end="2011-04-28",
        freq="D",
    )

    model = load_model("random_forest_v1.joblib")

    forecast_df = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 4: Match predictions with actual sales
    evaluation_df = forecast_df.merge(
        actual_future[
            ["product_id", "store_id", "date", "sales_quantity"]
        ],
        on=["product_id", "store_id", "date"],
        how="inner",
    )


    # Step 5: Calculate daily diagnostics
    evaluation_df["absolute_error"] = (
        evaluation_df["sales_quantity"]
        - evaluation_df["prediction"]
    ).abs()

    daily_metrics = (
        evaluation_df.groupby("date")
        .agg(
            actual_demand=("sales_quantity", "sum"),
            predicted_demand=("prediction", "sum"),
            mae=("absolute_error", "mean"),
        )
        .reset_index()
    )

    daily_metrics["forecast_bias"] = (
        daily_metrics["predicted_demand"]
        - daily_metrics["actual_demand"]
    )


    # Step 6: Display results
    print("\nDAILY FORECAST DIAGNOSTICS")
    print("=" * 85)

    print(
        daily_metrics.to_string(
            index=False,
            formatters={
                "actual_demand": "{:,.2f}".format,
                "predicted_demand": "{:,.2f}".format,
                "mae": "{:.4f}".format,
                "forecast_bias": "{:,.2f}".format,
            },
        )
    )


    # Step 7: Overall demand comparison
    print("\nOVERALL DEMAND COMPARISON")
    print("=" * 45)

    print(
        "Total actual demand:",
        evaluation_df["sales_quantity"].sum(),
    )

    print(
        "Total predicted demand:",
        evaluation_df["prediction"].sum(),
    )

    print(
        "Average actual demand per row:",
        evaluation_df["sales_quantity"].mean(),
    )

    print(
        "Average predicted demand per row:",
        evaluation_df["prediction"].mean(),
    )
