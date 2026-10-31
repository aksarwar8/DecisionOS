
from decisionos.ingestion import load_m5_data
from decisionos.preprocessing import preprocess_calendar
from decisionos.aggregation import aggregate_product_sales
from decisionos.feature_engineering import create_time_series_features
from decisionos.forecasting import naive_forecast, moving_average_forecast
from decisionos.ml_forecasting import train_random_forest
from decisionos.evaluation import evaluate_forecast

import pandas as pd
import matplotlib.pyplot as plt


# 1. Load and prepare data
sales, calendar, prices = load_m5_data()
calendar = preprocess_calendar(calendar)

product_sales = aggregate_product_sales(sales)

daily_sales = product_sales.filter(
    regex="^d_"
).sum(axis=0)


# 2. Create features
features = create_time_series_features(
    daily_sales,
    calendar
)


# 3. Train Random Forest
model, actual, rf_predictions = train_random_forest(features)


# 4. Generate baseline forecasts
split_index = int(len(features) * 0.8)

naive_predictions = naive_forecast(
    daily_sales
).iloc[split_index:]

ma_predictions = moving_average_forecast(
    daily_sales, window=7
).iloc[split_index:]


# 5. Align all models on the same test period
actual_values = actual.values

naive_predictions = naive_predictions.iloc[-len(actual_values):].values
ma_predictions = ma_predictions.iloc[-len(actual_values):].values


# 6. Evaluate models
results = []

for name, predictions in [
    ("Naive", naive_predictions),
    ("Moving Average", ma_predictions),
    ("Random Forest", rf_predictions)
]:

    mae, rmse = evaluate_forecast(
        actual_values, predictions
    )

    results.append({
        "Model": name,
        "MAE": mae,
        "RMSE": rmse
    })


results_df = pd.DataFrame(results)

print("\n--- MODEL COMPARISON ---")
print(results_df)


# 7. Visualize actual vs predicted
plt.figure(figsize=(14, 6))

plt.plot(
    actual.index,
    actual_values,
    label="Actual Sales"
)

plt.plot(
    actual.index,
    rf_predictions,
    label="Random Forest Prediction"
)

plt.title("DecisionOS: Actual vs Random Forest Forecast")
plt.xlabel("Date")
plt.ylabel("Units Sold")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()

plt.show()


# 8. Feature importance
importance = pd.Series(
    model.feature_importances_,
    index=[
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "weekday",
        "month"
    ]
).sort_values(ascending=False)

print("\n--- FEATURE IMPORTANCE ---")
print(importance)

importance.plot(kind="bar", figsize=(10, 5))

plt.title("Random Forest Feature Importance")
plt.ylabel("Importance")
plt.tight_layout()

plt.show()
