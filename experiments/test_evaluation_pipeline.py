if __name__ == "__main__":

    from src.decisionos.logging_config import configure_logging
    from src.decisionos.pipelines.evaluation import (
        evaluate_forecasting_run,
    )


    configure_logging()
    result = evaluate_forecasting_run(
        training_run_id="e40f828d365144209d5f7951feba7f14"
    )

    print("\nEVALUATION TEST SUMMARY")
    print("-" * 50)

    print("Training run:", result["training_run_id"])
    print("Evaluation run:", result["evaluation_run_id"])

    print("MAE:", round(result["MAE"], 4))
    print("RMSE:", round(result["RMSE"], 4))
    print("WAPE:", round(result["WAPE"], 2), "%")

    print("Evaluated rows:", result["evaluated_rows"])

    print(
        "Actual demand:",
        round(result["total_actual_demand"], 2),
    )

    print(
        "Predicted demand:",
        round(result["total_predicted_demand"], 2),
    )
