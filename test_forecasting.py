
import sys
from pathlib import Path
from decisionos.forecasting import moving_average_forecast

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "src"))

import pandas as pd

from decisionos.forecasting import naive_forecast
from decisionos.evaluation import evaluate_forecast


product_sales = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "product_sales.parquet"
)

daily_sales = product_sales[
    [col for col in product_sales.columns if col.startswith("d_")]
]

# Aggregate sales across all products
daily_total_sales = daily_sales.sum(axis=0)

# Time-based split: first 80% for training, last 20% for testing
split_index = int(len(daily_total_sales) * 0.8)

train = daily_total_sales.iloc[:split_index]
test = daily_total_sales.iloc[split_index:]

# Generate naive predictions
predictions = naive_forecast(daily_total_sales)

# Evaluate only on the test period
test_predictions = predictions.iloc[split_index:]

evaluate_forecast(
    test.values,
    test_predictions.values
)


# Generate 7-day moving average predictions
ma_predictions = moving_average_forecast(daily_total_sales, window=7)

ma_test_predictions = ma_predictions.iloc[split_index:]

evaluate_forecast(
    test.values,
    ma_test_predictions.values
)