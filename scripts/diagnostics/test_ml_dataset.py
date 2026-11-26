if __name__ == "__main__":

    from src.decisionos.data.pipeline import build_sales_dataset
    from src.decisionos.ml.dataset import prepare_ml_dataset


    # Step 1: Extract 90 days of sales data
    sales_df = build_sales_dataset(
        start_date="2011-01-29",
        end_date="2011-04-28",
    )


    # Step 2: Prepare ML dataset
    ml_df = prepare_ml_dataset(sales_df)


    # Step 3: Inspect results
    print("\nFinal columns:")
    print(ml_df.columns.tolist())

    print("\nMissing values:")
    print(ml_df.isnull().sum())

    print("\nDate range:")
    print(ml_df["date"].min(), "to", ml_df["date"].max())

    print("\nSample rows:")
    print(ml_df.head())
