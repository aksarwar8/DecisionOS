
from pathlib import Path
import pandas as pd
import joblib
from src.decisionos.baseline_forecasting import (
    seasonal_naive_forecast,
    evaluate_baseline
)

from src.decisionos.ingestion import load_m5_data
from src.decisionos.preprocessing import preprocess_calendar
from src.decisionos.aggregation import aggregate_product_sales
from src.decisionos.feature_engineering import (
    create_time_series_features
)
from src.decisionos.ml_forecasting import (
    train_random_forest
)
from src.decisionos.evaluation import evaluate_forecast
from src.decisionos.product_store_forecasting import (
    prepare_product_store_data,
    get_product_store_features,
    train_product_store_lightgbm
)


# ==========================================
# 1. Load data
# ==========================================

sales, calendar, prices = load_m5_data()

calendar = preprocess_calendar(calendar)


# ==========================================
# 2. Aggregate sales
# ==========================================

product_sales = aggregate_product_sales(sales)

daily_sales = product_sales.filter(
    regex="^d_"
).sum(axis=0)


# ==========================================
# 3. Create aggregate time-series features
# ==========================================

features = create_time_series_features(
    daily_sales,
    calendar
)


# ==========================================
# 4. Train aggregate Random Forest
# ==========================================

model, actual, predictions = train_random_forest(
    features
)


# ==========================================
# 5. Evaluate aggregate Random Forest
# ==========================================

print("\n========== AGGREGATE RANDOM FOREST ==========")

evaluate_forecast(
    actual.values,
    predictions
)


# ==========================================
# 6. Save aggregate Random Forest
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parent

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

model_path = MODEL_DIR / "random_forest_model.pkl"

joblib.dump(
    model,
    model_path
)

print("\nAggregate Random Forest saved successfully!")
print("Model location:", model_path)


# ==========================================
# 7. Load product-store features
# ==========================================

product_features_path = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "product_store_features.parquet"
)

product_features = pd.read_parquet(
    product_features_path
)

print("\nProduct-store dataset loaded successfully!")
print("Dataset shape:", product_features.shape)


# ==========================================
# 8. Chronological train-test split
# ==========================================

train, test, feature_columns, target_column = (
    prepare_product_store_data(
        product_features,
        test_days=28
    )
)

print("\n========== PRODUCT-STORE TIME SPLIT ==========")

print("Train max day:", train["day_number"].max())
print("Test min day:", test["day_number"].min())
print("Test max day:", test["day_number"].max())
print("Test unique days:", test["day_number"].nunique())

print("Training rows:", len(train))
print("Testing rows:", len(test))



# ==========================================
# 9. Evaluate Seasonal Naive Baseline
# ==========================================

print("\n========== PRODUCT-STORE BASELINE ==========")

baseline_actual, baseline_predictions = (
    seasonal_naive_forecast(test)
)

baseline_metrics = evaluate_baseline(
    baseline_actual,
    baseline_predictions
)


# ==========================================
# 9. Prepare LightGBM input features
# ==========================================

X_train, y_train, X_test, y_test = (
    get_product_store_features(
        train,
        test,
        feature_columns,
        target_column
    )
)

print("\nTraining feature shape:", X_train.shape)
print("Testing feature shape:", X_test.shape)


# ==========================================
# 10. Train product-store LightGBM
# ==========================================

print("\n========== PRODUCT-STORE LIGHTGBM ==========")

product_model, product_predictions = (
    train_product_store_lightgbm(
        X_train,
        y_train,
        X_test
    )
)

print("LightGBM training completed!")
print("Predictions shape:", product_predictions.shape)


# ==========================================
# 11. Evaluate product-store LightGBM
# ==========================================

print("\n========== PRODUCT-STORE EVALUATION ==========")

evaluate_forecast(
    y_test.values,
    product_predictions
)


# ==========================================
# 12. Save product-store LightGBM model
# ==========================================

product_model_path = (
    MODEL_DIR / "product_store_lightgbm_model.pkl"
)

joblib.dump(
    product_model,
    product_model_path
)

print("\nProduct-store LightGBM saved successfully!")
print("Model location:", product_model_path)


# ==========================================
# 13. Completion
# ==========================================

print("\n==========================================")
print("ALL FORECASTING EXPERIMENTS COMPLETED")
print("==========================================")
