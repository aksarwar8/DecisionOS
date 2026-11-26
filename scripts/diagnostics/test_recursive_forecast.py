if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.registry import load_model
    from src.decisionos.ml.forecast import recursive_forecast


    # Step 1: Load historical sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Keep actual history only through March 31
    history_df = sales_df[
        sales_df["date"] <= "2011-03-31"
    ].copy()


    # Step 3: Define the 28-day future horizon
    future_dates = pd.date_range(
        start="2011-04-01",
        end="2011-04-28",
        freq="D",
    )


    # Step 4: Load our trained Random Forest
    model = load_model(
        model_name="random_forest_v1.joblib",
    )


    # Step 5: Generate recursive predictions
    forecast_df = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )


    # Step 6: Inspect results
    print("\nForecast dataset shape:", forecast_df.shape)

    print("\nForecast date range:")
    print(
        forecast_df["date"].min(),
        "to",
        forecast_df["date"].max(),
    )

    print("\nPredictions by date:")
    print(
        forecast_df.groupby("date").size().head()
    )

    print("\nSample predictions:")
    print(forecast_df.head(20).to_string(index=False))

    print(
        "\nMissing predictions:",
        forecast_df["prediction"].isna().sum(),
    )

    print(
        "\nNegative predictions:",
        (forecast_df["prediction"] < 0).sum(),
    )
