
import pandas as pd


def create_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate time-based features from a date column.

    Required column:
        date
    """
    if "date" not in df.columns:
        raise ValueError("DataFrame must contain a 'date' column.")

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])

    result["year"] = result["date"].dt.year
    result["quarter"] = result["date"].dt.quarter
    result["month"] = result["date"].dt.month
    result["week"] = result["date"].dt.isocalendar().week.astype("int16")
    result["day"] = result["date"].dt.day
    result["day_of_week"] = result["date"].dt.dayofweek
    result["is_weekend"] = (
        result["date"].dt.dayofweek >= 5
    ).astype("int8")

    return result
