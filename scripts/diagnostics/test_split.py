if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.features.pipeline import build_features
    from src.decisionos.ml.split import temporal_split


    # Extract 90 days of historical sales
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )

    # Generate features
    featured_df = build_features(sales_df)

    # Chronological split
    train_df, validation_df, test_df = temporal_split(
        featured_df,
        train_end="2011-03-31",
        validation_end="2011-04-14",
    )

    print("Train:", train_df.shape)
    print("Validation:", validation_df.shape)
    print("Test:", test_df.shape)

    print("\nTrain date range:")
    print(train_df["date"].min(), "to", train_df["date"].max())

    print("\nValidation date range:")
    print(validation_df["date"].min(), "to", validation_df["date"].max())

    print("\nTest date range:")
    print(test_df["date"].min(), "to", test_df["date"].max())
