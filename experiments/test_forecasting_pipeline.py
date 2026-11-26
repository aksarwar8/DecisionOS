if __name__ == "__main__":

    from src.decisionos.logging_config import configure_logging
    from src.decisionos.pipelines.forecasting import (
        run_forecasting_pipeline,
    )

    configure_logging()
    result = run_forecasting_pipeline(
        history_start_date="2011-01-29",
        history_end_date="2011-03-31",
        forecast_start_date="2011-04-01",
        forecast_end_date="2011-04-07",
        model_name="decisionos_pipeline_v1.joblib",
    )

    print("\nPIPELINE TEST SUMMARY")
    print("-" * 50)

    print("Training rows:", result["training_rows"])
    print("Forecast rows:", result["forecast_rows"])
    print("Forecast horizon:", result["forecast_horizon"])
    print(
        "Total predicted demand:",
        round(result["total_predicted_demand"], 2),
    )

    print("\nForecast sample:")
    print(result["forecasts"].head(10))
