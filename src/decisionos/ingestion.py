
from pathlib import Path
import pandas as pd


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Raw data directory
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def load_m5_data():
    """Load the three raw M5 datasets."""

    sales = pd.read_csv(
        RAW_DATA_DIR / "sales_train_validation.csv"
    )

    calendar = pd.read_csv(
        RAW_DATA_DIR / "calendar.csv"
    )

    prices = pd.read_csv(
        RAW_DATA_DIR / "sell_prices.csv"
    )

    return sales, calendar, prices
