
from pathlib import Path
import joblib

from decisionos.ingestion import load_m5_data
from decisionos.preprocessing import preprocess_calendar
from decisionos.aggregation import aggregate_product_sales
from decisionos.feature_engineering import create_time_series_features
from decisionos.ml_forecasting import train_random_forest
from decisionos.evaluation import evaluate_forecast


# 1. Load data
sales, calendar, prices = load_m5_data()

calendar = preprocess_calendar(calendar)


# 2. Aggregate sales
product_sales = aggregate_product_sales(sales)

daily_sales = product_sales.filter(
    regex="^d_"
).sum(axis=0)


# 3. Create features
features = create_time_series_features(
    daily_sales,
    calendar
)


# 4. Train model
model, actual, predictions = train_random_forest(features)


# 5. Evaluate model
evaluate_forecast(actual.values, predictions)


# 6. Save model
PROJECT_ROOT = Path(__file__).resolve().parent

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

joblib.dump(
    model,
    MODEL_DIR / "random_forest_model.pkl"
)

print("Random Forest model saved successfully!")
