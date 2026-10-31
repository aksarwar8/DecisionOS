
from decisionos.ingestion import load_m5_data
from decisionos.preprocessing import preprocess_calendar
from decisionos.aggregation import aggregate_product_sales
from decisionos.feature_engineering import create_product_features


# 1. Load data
sales, calendar, prices = load_m5_data()

calendar = preprocess_calendar(calendar)


# 2. Aggregate across stores for each product
product_sales = aggregate_product_sales(sales)


# 3. Generate product-level features
features = create_product_features(
    product_sales,
    calendar
)


# 4. Inspect dataset
print("\n--- Product-Level Dataset ---")

print("Shape:", features.shape)

print("\nFirst 5 rows:")
print(features.head())

print("\nNumber of unique products:")
print(features["item_id"].nunique())

print("\nMemory usage (MB):")
print(
    round(
        features.memory_usage(deep=True).sum() / 1024**2,
        2
    )
)
