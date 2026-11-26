if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.forecast import recursive_forecast


    # Step 1: Load data
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


    # Step 2: Generate Random Forest forecasts
    model = load_model("random_forest_v1.joblib")

    rf_forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 3: Generate Historical Mean forecasts
    historical_means = (
        history_df.groupby(
            ["product_id", "store_id"]
        )["sales_quantity"]
        .mean()
        .reset_index(name="mean_prediction")
    )

    mean_forecasts = actual_future[
        ["product_id", "store_id", "date"]
    ].merge(
        historical_means,
        on=["product_id", "store_id"],
        how="left",
    )


    # Step 4: Match all predictions with actual sales
    comparison = rf_forecasts.merge(
        mean_forecasts,
        on=["product_id", "store_id", "date"],
    )

    comparison = comparison.merge(
        actual_future[
            ["product_id", "store_id", "date", "sales_quantity"]
        ],
        on=["product_id", "store_id", "date"],
    )


    # Step 5: Classify demand using historical averages
    product_demand = historical_means.copy()

    product_demand["demand_segment"] = pd.cut(
        product_demand["mean_prediction"],
        bins=[-float("inf"), 0, 1, 5, float("inf")],
        labels=[
            "Zero average",
            "Low demand",
            "Medium demand",
            "High demand",
        ],
    )

    comparison = comparison.merge(
        product_demand[
            ["product_id", "store_id", "demand_segment"]
        ],
        on=["product_id", "store_id"],
    )


    # Step 6: Compare models within each segment
    results = []

    for segment, group in comparison.groupby(
        "demand_segment",
        observed=True,
    ):

        for model_name, prediction_column in [
            ("Random Forest", "prediction"),
            ("Historical Mean", "mean_prediction"),
        ]:

            errors = (
                group["sales_quantity"] - group[prediction_column]
            ).abs()

            actual_total = group["sales_quantity"].abs().sum()

            wape = (
                errors.sum() / actual_total * 100
                if actual_total > 0
                else float("nan")
            )

            results.append({
                "segment": str(segment),
                "model": model_name,
                "MAE": errors.mean(),
                "WAPE": wape,
                "predicted_demand": group[prediction_column].sum(),
                "actual_demand": group["sales_quantity"].sum(),
            })


    # Step 7: Display comparison
    results_df = pd.DataFrame(results)

    print("\nSEGMENT-LEVEL MODEL COMPARISON")
    print("=" * 100)

    print(
        results_df.to_string(
            index=False,
            formatters={
                "MAE": "{:.4f}".format,
                "WAPE": lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A",
                "predicted_demand": "{:,.2f}".format,
                "actual_demand": "{:,.2f}".format,
            },
        )
    )
