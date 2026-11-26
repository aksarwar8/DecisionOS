if __name__ == "__main__":

    import gc
    import numpy as np
    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.train import train_random_forest
    from src.decisionos.ml.forecast import recursive_forecast
    from src.decisionos.ml.hybrid import hybrid_forecast
    from src.decisionos.ml.evaluate import evaluate_forecasts


    # --------------------------------------------------
    # 1. Configuration
    # --------------------------------------------------

    DATA_START = "2011-01-29"
    DATA_END = "2011-04-28"

    FOLDS = [
        ("2011-03-31", "2011-04-01", "2011-04-07"),
        ("2011-04-07", "2011-04-08", "2011-04-14"),
        ("2011-04-14", "2011-04-15", "2011-04-21"),
        ("2011-04-21", "2011-04-22", "2011-04-28"),
    ]


    # --------------------------------------------------
    # 2. Baseline forecasting functions
    # --------------------------------------------------

    def historical_mean_forecast(history_df, future_dates):

        means = (
            history_df
            .groupby(["product_id", "store_id"])["sales_quantity"]
            .mean()
            .reset_index(name="prediction")
        )

        dates = pd.DataFrame({"date": future_dates})

        means["key"] = 1
        dates["key"] = 1

        forecasts = means.merge(dates, on="key").drop(columns="key")

        return forecasts[
            ["product_id", "store_id", "date", "prediction"]
        ]


    def seasonal_naive_recursive(history_df, future_dates):

        records = []

        grouped = history_df.sort_values("date").groupby(
            ["product_id", "store_id"]
        )

        for (product_id, store_id), group in grouped:

            values = group["sales_quantity"].to_list()

            for forecast_date in future_dates:

                prediction = values[-7]

                records.append({
                    "product_id": product_id,
                    "store_id": store_id,
                    "date": forecast_date,
                    "prediction": prediction
                })

                values.append(prediction)

        return pd.DataFrame(records)


    # --------------------------------------------------
    # 3. Load historical dataset
    # --------------------------------------------------

    print("\nLoading sales dataset...")

    all_sales = build_sales_dataset(
        start_date=DATA_START,
        end_date=DATA_END
    )

    print("Complete dataset:", all_sales.shape)
    print(
        "Date range:",
        all_sales["date"].min(),
        "to",
        all_sales["date"].max()
    )


    # --------------------------------------------------
    # 4. Run rolling-origin backtesting
    # --------------------------------------------------

    all_results = []

    for fold_number, (origin, forecast_start, forecast_end) in enumerate(
        FOLDS, start=1
    ):

        print("\n" + "=" * 75)
        print(f"FOLD {fold_number}")
        print("=" * 75)

        origin = pd.Timestamp(origin)
        forecast_start = pd.Timestamp(forecast_start)
        forecast_end = pd.Timestamp(forecast_end)

        future_dates = pd.date_range(
            start=forecast_start,
            end=forecast_end,
            freq="D"
        )

        # Only use information available at this forecast origin.
        history_df = all_sales[
            all_sales["date"] <= origin
        ].copy()

        actual_df = all_sales[
            (all_sales["date"] >= forecast_start)
            & (all_sales["date"] <= forecast_end)
        ].copy()

        print("History rows:", len(history_df))
        print("Actual test rows:", len(actual_df))
        print("Forecast dates:", len(future_dates))

        # Prepare training data and retrain Random Forest.
        print("\nPreparing training dataset...")

        train_df = prepare_ml_dataset(history_df)

        print("Training rows:", len(train_df))

        print("\nTraining Random Forest...")

        model = train_random_forest(train_df)

        print("Random Forest training completed.")

        del train_df
        gc.collect()

        # --------------------------------------------------
        # 5. Generate four forecasts
        # --------------------------------------------------

        print("\nGenerating Historical Mean forecast...")

        mean_forecast = historical_mean_forecast(
            history_df, future_dates
        )

        print("Generating Seasonal Naive forecast...")

        seasonal_forecast = seasonal_naive_recursive(
            history_df, future_dates
        )

        print("Generating Random Forest forecast...")

        rf_forecast = recursive_forecast(
            model,
            history_df,
            future_dates
        )

        print("Generating Hybrid forecast...")

        hybrid_result = hybrid_forecast(
            model,
            history_df,
            future_dates
        )

        # --------------------------------------------------
        # 6. Evaluate each model
        # --------------------------------------------------

        forecasts = {
            "Historical Mean": mean_forecast,
            "Seasonal Naive": seasonal_forecast,
            "Random Forest": rf_forecast,
            "Hybrid": hybrid_result
        }

        for model_name, forecast_df in forecasts.items():

            comparison = actual_df[
                ["product_id", "store_id", "date", "sales_quantity"]
            ].merge(
                forecast_df[
                    ["product_id", "store_id", "date", "prediction"]
                ],
                on=["product_id", "store_id", "date"],
                how="inner",
                validate="one_to_one"
            )

            if len(comparison) != len(actual_df):
                raise ValueError(
                    f"{model_name}: prediction rows do not match "
                    f"actual rows in fold {fold_number}."
                )

            metrics = evaluate_forecasts(
                comparison["sales_quantity"],
                comparison["prediction"]
            )

            result = {
                "Fold": fold_number,
                "Forecast Period": (
                    f"{forecast_start.date()} to {forecast_end.date()}"
                ),
                "Model": model_name,
                **metrics,
                "Total Predicted Demand": comparison["prediction"].sum()
            }

            all_results.append(result)

            print(
                f"{model_name}: "
                f"MAE={metrics['MAE']:.4f}, "
                f"RMSE={metrics['RMSE']:.4f}, "
                f"WAPE={metrics['WAPE']:.2f}%"
            )

        del history_df, actual_df
        del model, forecasts
        gc.collect()


    # --------------------------------------------------
    # 7. Display final results
    # --------------------------------------------------

    results_df = pd.DataFrame(all_results)

    print("\n\nROLLING-ORIGIN BACKTEST RESULTS")
    print("=" * 100)

    print(
        results_df[
            [
                "Fold",
                "Forecast Period",
                "Model",
                "MAE",
                "RMSE",
                "WAPE",
                "Total Predicted Demand"
            ]
        ].to_string(index=False, float_format=lambda x: f"{x:.4f}")
    )

    # Average metrics across all four folds.
    average_results = (
        results_df
        .groupby("Model")[["MAE", "RMSE", "WAPE"]]
        .mean()
        .sort_values("WAPE")
    )

    print("\nAVERAGE PERFORMANCE ACROSS FOUR FOLDS")
    print("=" * 75)
    print(average_results.to_string(float_format=lambda x: f"{x:.4f}"))

    # Save detailed results.
    output_path = (
        "data/processed/rolling_origin_backtest_results.csv"
    )

    results_df.to_csv(output_path, index=False)

    print(f"\nResults saved to: {output_path}")
