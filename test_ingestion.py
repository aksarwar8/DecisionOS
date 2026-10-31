
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "src"))

from decisionos.aggregation import aggregate_product_sales
from decisionos.time_series import convert_to_long_format

import pandas as pd

# Load processed sales and calendar
sales = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "sales.parquet"
)

calendar = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "calendar.parquet"
)

# Use a small sample first
sales_sample = sales.head(100)

# Step 1: Aggregate
product_sales = aggregate_product_sales(sales_sample)

print("Aggregated shape:", product_sales.shape)

# Step 2: Convert to long format
sales_long = convert_to_long_format(
    product_sales,
    calendar
)

print("Long format shape:", sales_long.shape)
print(sales_long.head())

print("\nTime-series transformation successful!")
