
import pandas as pd
from pathlib import Path


def create_time_series_features(daily_total_sales, calendar):

    df = daily_total_sales.rename("sales").reset_index()
    df.columns = ["day", "sales"]

    # Add calendar features
    df = df.merge(
        calendar[["d", "weekday", "month"]].rename(
            columns={"d": "day"}
        ),
        on="day",
        how="left"
    )

    # Lag features
    df["lag_1"] = df["sales"].shift(1)
    df["lag_7"] = df["sales"].shift(7)
    df["lag_14"] = df["sales"].shift(14)

    # Rolling mean feature
    df["rolling_mean_7"] = (
        df["sales"].shift(1).rolling(window=7).mean()
    )

    # Target variable
    df["target"] = df["sales"]

    # Remove rows containing NaN from lag features
    df = df.dropna()

    return df


def create_product_features(product_sales, calendar):

    day_columns = [
        col for col in product_sales.columns
        if col.startswith("d_")
    ]

    # Convert wide data into long format
    df = product_sales.melt(
        id_vars=[
            "item_id",
            "cat_id",
            "dept_id",
            "store_id"
        ],
        value_vars=day_columns,
        var_name="day",
        value_name="sales"
    )

    # Optimize memory usage using categorical data types
    df["item_id"] = df["item_id"].astype("category")
    df["cat_id"] = df["cat_id"].astype("category")
    df["dept_id"] = df["dept_id"].astype("category")
    df["store_id"] = df["store_id"].astype("category")

    # Convert sales to 32-bit integer
    df["sales"] = df["sales"].astype("int32")

    # Extract numerical day for correct chronological sorting
    df["day_number"] = (
        df["day"].str.replace("d_", "", regex=False)
        .astype("int32")
    )

    # Merge calendar features
    calendar_features = calendar[
        ["d", "weekday", "month"]
    ].rename(columns={"d": "day"})

    df = df.merge(
        calendar_features,
        on="day",
        how="left"
    )

    # Sort by product, store, and chronological day
    df = df.sort_values(
        ["item_id", "store_id", "day_number"]
    ).reset_index(drop=True)

    # Group sales by product-store combination
    grouped_sales = df.groupby(
        ["item_id", "store_id"],
        observed=True
    )["sales"]

    # Lag features
    df["lag_1"] = grouped_sales.shift(1)
    df["lag_7"] = grouped_sales.shift(7)
    df["lag_14"] = grouped_sales.shift(14)

    # Rolling mean of previous 7 days
    df["rolling_mean_7"] = (
        df.groupby(
            ["item_id", "store_id"],
            observed=True
        )["sales"]
        .transform(
            lambda x: x.shift(1).rolling(window=7).mean()
        )
    )

    # Encode weekdays
    weekday_mapping = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6
    }

    df["weekday"] = df["weekday"].map(weekday_mapping)

    # Target variable
    df["target"] = df["sales"]

    # Reduce numerical feature memory
    numerical_columns = [
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "target"
    ]

    df[numerical_columns] = df[numerical_columns].astype("float32")

    # Remove rows with missing lag values
    df = df.dropna()

    # Save optimized features to Parquet
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    df.to_parquet(
        output_dir / "product_store_features.parquet",
        index=False
    )

    print("Optimized features saved to Parquet.")

    return df
