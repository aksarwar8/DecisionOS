if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.train import train_random_forest
    from src.decisionos.ml.train import FEATURE_COLUMNS
    from src.decisionos.ml.forecast import recursive_forecast


    # Step 1: Load data through March 31
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-03-31",
    )

    ml_df = prepare_ml_dataset(sales_df)


    # Step 2: Define training and validation periods
    train_end = pd.Timestamp("2011-03-17")

    train_df = ml_df[
        ml_df["date"] <= train_end
    ].copy()

    history_df = sales_df[
        sales_df["date"] <= train_end
    ].copy()

    validation_actual = sales_df[
        sales_df["date"] > train_end
    ].copy()

    validation_dates = pd.date_range(
        start="2011-03-18",
        end="2011-03-31",
        freq="D",
    )

    print("Training rows:", len(train_df))
    print("Validation rows:", len(validation_actual))


    # Step 3: Calculate historical means using training data only
    historical_means = (
        history_df.groupby(
            ["product_id", "store_id"]
        )["sales_quantity"]
        .mean()
        .reset_index(name="historical_average")
    )


    # Step 4: Assign demand segments using training averages
    historical_means["demand_segment"] = pd.cut(
        historical_means["historical_average"],
        bins=[-float("inf"), 0, 1, 5, float("inf")],
        labels=[
            "Zero average",
            "Low demand",
            "Medium demand",
            "High demand",
        ],
    )


    # Step 5: Train Random Forest using training data only
    model = train_random_forest(
        train_df=train_df,
        n_estimators=100,
    )


    # Step 6: Generate 14-day recursive RF forecasts
    rf_forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=validation_dates,
    )


    # Step 7: Generate Historical Mean forecasts
    mean_forecasts = validation_actual[
        ["product_id", "store_id", "date"]
    ].merge(
        historical_means[
            ["product_id", "store_id", "historical_average"]
        ],
        on=["product_id", "store_id"],
        how="left",
    )

    mean_forecasts = mean_forecasts.rename(
        columns={"historical_average": "mean_prediction"}
    )


    # Step 8: Combine predictions and actual values
    comparison = rf_forecasts.merge(
        mean_forecasts,
        on=["product_id", "store_id", "date"],
    )

    comparison = comparison.merge(
        validation_actual[
            ["product_id", "store_id", "date", "sales_quantity"]
        ],
        on=["product_id", "store_id", "date"],
    )

    comparison = comparison.merge(
        historical_means[
            ["product_id", "store_id", "demand_segment"]
        ],
        on=["product_id", "store_id"],
    )


    # Step 9: Compare models within each segment
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
            })


    results_df = pd.DataFrame(results)


    # Step 10: Select a model for each segment
    print("\nVALIDATION MODEL COMPARISON")
    print("=" * 65)

    print(
        results_df.to_string(
            index=False,
            formatters={
                "MAE": "{:.4f}".format,
                "WAPE": lambda x: (
                    f"{x:.2f}%" if pd.notna(x) else "N/A"
                ),
            },
        )
    )


    print("\nSELECTED MODEL PER SEGMENT")
    print("=" * 65)

    for segment, group in results_df.groupby("segment"):

        valid_wape = group.dropna(subset=["WAPE"])

        if not valid_wape.empty:
            winner = valid_wape.loc[valid_wape["WAPE"].idxmin()]
            selection_metric = "WAPE"
        else:
            winner = group.loc[group["MAE"].idxmin()]
            selection_metric = "MAE (WAPE unavailable)"

        print(
            f"{segment}: {winner['model']} "
            f"(selected using {selection_metric})"
        )
