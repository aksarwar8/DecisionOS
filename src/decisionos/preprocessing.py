
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


def preprocess_calendar(calendar):
    """Clean and prepare calendar data."""

    calendar = calendar.copy()

    # Convert date column to datetime
    calendar["date"] = pd.to_datetime(calendar["date"])

    # Replace missing event names with No Event
    calendar["event_name_1"] = (
        calendar["event_name_1"].fillna("No Event")
    )

    calendar["event_name_2"] = (
        calendar["event_name_2"].fillna("No Event")
    )

    return calendar


def save_processed_data(sales, calendar, prices):
    """Save processed datasets in Parquet format."""

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    sales.to_parquet(
        PROCESSED_DATA_DIR / "sales.parquet",
        index=False
    )

    calendar.to_parquet(
        PROCESSED_DATA_DIR / "calendar.parquet",
        index=False
    )

    prices.to_parquet(
        PROCESSED_DATA_DIR / "prices.parquet",
        index=False
    )

    print("Processed datasets saved successfully.")


def save_product_sales(product_sales):
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    product_sales.to_parquet(
        PROCESSED_DATA_DIR / "product_sales.parquet",
        index=False
    )

    print("Product-level sales data saved successfully.")