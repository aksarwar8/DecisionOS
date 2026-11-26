if __name__ == "__main__":

    import pandas as pd

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset
    from src.decisionos.ml.train import train_random_forest
    from src.decisionos.ml.registry import save_model
    from src.decisionos.ml.hybrid import hybrid_forecast


    # Step 1: Load all pre-test historical data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-03-31",
    )


    # Step 2: Prepare the ML training dataset
    ml_df = prepare_ml_dataset(sales_df)


    # Step 3: Train Random Forest using all available
    # pre-April training observations
    model = train_random_forest(
        train_df=ml_df,
        n_estimators=100,
    )


    # Step 4: Save the hybrid system's Random Forest model
    save_model(
        model,
        model_name="random_forest_hybrid_v1.joblib",
    )


    # Step 5: Define the 28-day forecasting horizon
    future_dates = pd.date_range(
        start="2011-04-01",
        end="2011-04-28",
        freq="D",
    )


    # Step 6: Generate hybrid forecasts
    forecast_df = hybrid_forecast(
        model=model,
        history_df=sales_df,
        future_dates=future_dates,
    )


    # Step 7: Inspect forecasts
    print("\nHYBRID FORECAST RESULTS")
    print("=" * 50)

    print("Dataset shape:", forecast_df.shape)

    print("\nModel selection counts:")
    print(
        forecast_df.groupby(
            ["demand_segment", "selected_model"],
            observed=True,
        ).size()
    )

    print("\nSample predictions:")
    print(forecast_df.head(20).to_string(index=False))

    print("\nTotal predicted demand:")
    print(forecast_df["prediction"].sum())

    print("\nMissing predictions:")
    print(forecast_df["prediction"].isna().sum())
