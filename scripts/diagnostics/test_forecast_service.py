if __name__ == "__main__":

    from backend.services.forecast_service import (
        generate_product_forecast,
    )


    forecast = generate_product_forecast(
        product_id=1,
        store_id=1,
        horizon=7,
    )

    print("\nForecast results:")
    print(forecast.to_string(index=False))

    print("\nForecast summary:")
    print("Rows:", len(forecast))
    print("Total predicted demand:", forecast["prediction"].sum())
    print("Selected models:", forecast["selected_model"].unique())
    print("Demand segments:", forecast["demand_segment"].unique())
