if __name__ == "__main__":

    from src.decisionos.data.extract import (
        extract_calendar,
        extract_prices,
        extract_sales,
    )

    from src.decisionos.data.validate import validate_dataframe


    # 1. Calendar validation
    calendar_df = extract_calendar()

    validate_dataframe(
        calendar_df,
        required_columns=["id", "date", "wm_yr_wk"],
        name="Calendar",
    )


    # 2. Prices validation
    prices_df = extract_prices()

    validate_dataframe(
        prices_df,
        required_columns=[
            "product_id",
            "store_id",
            "wm_yr_wk",
            "sell_price",
        ],
        name="Prices",
    )


    # 3. Sales validation (only 7 days)
    sales_df = extract_sales(
        start_date="2011-01-29",
        end_date="2011-02-04",
    )

    validate_dataframe(
        sales_df,
        required_columns=[
            "product_id",
            "store_id",
            "date",
            "sales_quantity",
        ],
        name="Sales",
    )
    from src.decisionos.data.transform import (
        transform_sales,
        aggregate_daily_sales,
    )


    # 4. Transform sales data
    transformed_sales = transform_sales(sales_df)

    print("\nTransformed sales:")
    print(transformed_sales.head())
    print("Shape:", transformed_sales.shape)
    print("Columns:", transformed_sales.columns.tolist())


    # 5. Test daily aggregation
    daily_sales = aggregate_daily_sales(transformed_sales)

    print("\nDaily aggregation:")
    print(daily_sales.head())
    print("Shape:", daily_sales.shape)


    from src.decisionos.data.pipeline import build_sales_dataset


    # 6. Test the complete data pipeline
    final_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-02-04",
    )

    print("\nComplete pipeline:")
    print(final_df.head())
    print("Shape:", final_df.shape)


    from src.decisionos.features.time_features import create_time_features


    time_feature_df = create_time_features(final_df)

    print("\nTime features:")
    print(
        time_feature_df[
            ["date", "year", "quarter", "month",
             "week", "day_of_week", "is_weekend"]
        ].head()
    )

    print("Shape:", time_feature_df.shape)

    from src.decisionos.features.lag_features import create_lag_features


    # Test lag and rolling features
    lag_df = create_lag_features(final_df)

    print("\nLag features:")
    print(
        lag_df[
            [
                "product_id",
                "store_id",
                "date",
                "sales_quantity",
                "lag_7",
                "lag_14",
                "lag_28",
                "rolling_mean_7",
                "rolling_mean_28",
                "rolling_std_7",
            ]
        ].head(35)
    )

    print("Shape:", lag_df.shape)
    print("Missing values in lag features:")
    print(
        lag_df[
            ["lag_7", "lag_14", "lag_28",
             "rolling_mean_7", "rolling_mean_28", "rolling_std_7"]
        ].isnull().sum()
    )
