
import pandas as pd


def temporal_split(
    df: pd.DataFrame,
    train_end: str,
    validation_end: str,
):
    """
    Split time-series data chronologically.

    Train:      date <= train_end
    Validation:  train_end < date <= validation_end
    Test:        date > validation_end
    """
    if "date" not in df.columns:
        raise ValueError("DataFrame must contain a 'date' column.")

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])

    train_end = pd.to_datetime(train_end)
    validation_end = pd.to_datetime(validation_end)

    if train_end >= validation_end:
        raise ValueError(
            "train_end must be earlier than validation_end."
        )

    train_df = result[result["date"] <= train_end].copy()

    validation_df = result[
        (result["date"] > train_end)
        & (result["date"] <= validation_end)
    ].copy()

    test_df = result[result["date"] > validation_end].copy()

    return train_df, validation_df, test_df
