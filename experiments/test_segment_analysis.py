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


    # Step 2: Generate forecasts
    model = load_model("random_forest_v1.joblib")

    forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 3: Match actual and predicted demand
    evaluation = forecasts.merge(
        actual_future[
            ["product_id", "store_id", "date", "sales_quantity"]
        ],
        on=["product_id", "store_id", "date"],
        how="inner",
    )

    evaluation["absolute_error"] = (
        evaluation["sales_quantity"]
        - evaluation["prediction"]
    ).abs()


    # Step 4: Classify products by historical demand
    product_demand = (
        history_df.groupby("product_id")["sales_quantity"]
        .mean()
        .reset_index(name="historical_average")
    )

    product_demand["demand_segment"] = pd.cut(
        product_demand["historical_average"],
        bins=[-float("inf"), 0, 1, 5, float("inf")],
        labels=[
            "Zero average",
            "Low demand",
            "Medium demand",
            "High demand",
        ],
    )


    evaluation = evaluation.merge(
        product_demand[
            ["product_id", "demand_segment"]
        ],
        on="product_id",
    )


    # Step 5: Analyze each demand segment
    segment_results = (
        evaluation.groupby("demand_segment", observed=False)
        .apply(
            lambda group: pd.Series({
                "rows": len(group),
                "actual_demand": group["sales_quantity"].sum(),
                "predicted_demand": group["prediction"].sum(),
                "MAE": group["absolute_error"].mean(),
                "WAPE": (
                    group["absolute_error"].sum()
                    / group["sales_quantity"].abs().sum()
                    * 100
                    if group["sales_quantity"].abs().sum() > 0
                    else float("nan")
                ),
            }),
            include_groups=False,
        )
        .reset_index()
    )


    print("\nRANDOM FOREST SEGMENT ANALYSIS")
    print("=" * 85)

    print(
        segment_results.to_string(
            index=False,
            formatters={
                "actual_demand": "{:,.2f}".format,
                "predicted_demand": "{:,.2f}".format,
                "MAE": "{:.4f}".format,
                "WAPE": "{:.2f}%".format,
            },
        )
    )
