
from decisionos.ingestion import load_m5_data
from decisionos.preprocessing import preprocess_calendar
from decisionos.aggregation import aggregate_product_sales
from decisionos.feature_engineering import create_time_series_features
from decisionos.tuning import tune_lightgbm
from decisionos.evaluation import evaluate_forecast


# Load data
sales, calendar, prices = load_m5_data()

calendar = preprocess_calendar(calendar)

# Aggregate sales
product_sales = aggregate_product_sales(sales)

daily_sales = product_sales.filter(
    regex="^d_"
).sum(axis=0)

# Create features
features = create_time_series_features(
    daily_sales,
    calendar
)

# Tune LightGBM
model, actual, predictions = tune_lightgbm(features)

# Evaluate final test set
evaluate_forecast(actual.values, predictions)
