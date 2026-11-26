if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.features.lag_features import create_lag_features


    # Extract 35 days of historical sales
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-03-04",
    )

    print("Base dataset shape:", sales_df.shape)


    # Generate lag and rolling features
    lag_df = create_lag_features(sales_df)

    feature_columns = [
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_28",
        "rolling_std_7",
    ]

    print("\nLag feature sample:")
    print(
        lag_df[
            [
                "product_id",
                "store_id",
                "date",
                "sales_quantity",
                *feature_columns,
            ]
        ].head(35)
    )

    print("\nMissing values:")
    print(lag_df[feature_columns].isnull().sum())

    print("\nDataset shape after feature engineering:")
    print(lag_df.shape)
