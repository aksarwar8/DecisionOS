
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Read saved Parquet files
sales = pd.read_parquet(PROCESSED_DIR / "sales.parquet")
calendar = pd.read_parquet(PROCESSED_DIR / "calendar.parquet")
prices = pd.read_parquet(PROCESSED_DIR / "prices.parquet")

# Verify
print("Sales shape:", sales.shape)
print("Calendar shape:", calendar.shape)
print("Prices shape:", prices.shape)

print("\nCalendar date dtype:", calendar["date"].dtype)

print("\nParquet verification successful!")
