
from decisionos.ingestion import load_m5_data
from decisionos.preprocessing import preprocess_calendar
from decisionos.feature_engineering import create_time_series_features
from decisionos.aggregation import aggregate_product_sales
from decisionos.analysis import analyze_product_sales


sales, calendar, prices = load_m5_data()

calendar = preprocess_calendar(calendar)

product_sales = aggregate_product_sales(sales)

daily_sales = product_sales.filter(
    regex="^d_"
).sum(axis=0)

features = create_time_series_features(
    daily_sales,
    calendar
)

print(features.head())
print("\nDataset shape:", features.shape)
print("\nColumns:", features.columns.tolist())
