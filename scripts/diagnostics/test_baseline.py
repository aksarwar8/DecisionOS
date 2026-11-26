if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.baseline import seasonal_naive_forecast


    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )

    forecast_df = seasonal_naive_forecast(
        sales_df,
        seasonal_period=7,
    )

    print("Dataset shape:", forecast_df.shape)

    print("\nSample predictions:")
    print(
        forecast_df[
            [
                "product_id",
                "store_id",
                "date",
                "sales_quantity",
                "prediction",
            ]
        ].head(20)
    )

    print("\nMissing predictions:", forecast_df["prediction"].isnull().sum())
    print("Valid predictions:", forecast_df["prediction"].notnull().sum())
