
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "src"))

import pandas as pd
from decisionos.analysis import analyze_product_sales

product_sales = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "product_sales.parquet"
)

daily_sales = analyze_product_sales(product_sales)

print("\nDaily sales matrix shape:", daily_sales.shape)

print("\nFirst 5 days of aggregate sales:")
print(daily_sales.sum(axis=0).head())




import matplotlib.pyplot as plt

# Calculate total sales across all products for each day
daily_total_sales = daily_sales.sum(axis=0)

# Plot daily sales
plt.figure(figsize=(15, 5))

plt.plot(daily_total_sales.values)

plt.title("DecisionOS - Daily Total Sales")
plt.xlabel("Day")
plt.ylabel("Units Sold")
plt.grid(True)

plt.show()



from decisionos.seasonality import analyze_weekly_seasonality

calendar = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "calendar.parquet"
)

weekday_sales = analyze_weekly_seasonality(
    daily_total_sales,
    calendar
)

weekday_sales.plot(kind="bar", figsize=(10, 5))

plt.title("DecisionOS - Average Sales by Weekday")
plt.xlabel("Weekday")
plt.ylabel("Average Units Sold")
plt.grid(axis="y")

plt.show()



from decisionos.seasonality import analyze_monthly_seasonality

monthly_sales = analyze_monthly_seasonality(
    daily_total_sales,
    calendar
)

monthly_sales.plot(kind="bar", figsize=(10, 5))

plt.title("DecisionOS - Average Sales by Month")
plt.xlabel("Month")
plt.ylabel("Average Units Sold")
plt.grid(axis="y")

plt.show()
