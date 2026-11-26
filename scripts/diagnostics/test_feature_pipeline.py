if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.features.pipeline import build_features


    # Extract 35 days of sales
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-03-04",
    )

    # Generate all features
    featured_df = build_features(sales_df)

    print("Original shape:", sales_df.shape)
    print("Featured shape:", featured_df.shape)

    print("\nAll generated features:")
    print(featured_df.columns.tolist())

    print("\nSample:")
    print(
        featured_df[
            [
                "product_id",
                "store_id",
                "date",
                "sales_quantity",
                "day_of_week",
                "is_weekend",
                "lag_7",
                "lag_14",
                "lag_28",
                "rolling_mean_7",
                "rolling_mean_28",
        ]
        ].head(35)
    )
