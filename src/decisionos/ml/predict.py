
import pandas as pd

from src.decisionos.ml.train import FEATURE_COLUMNS


def predict_demand(
    model,
    input_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate demand predictions using a trained model.

    Required input:
        A DataFrame containing all FEATURE_COLUMNS.

    Returns:
        A copy of the input DataFrame with a prediction column.
    """

    missing_columns = (
        set(FEATURE_COLUMNS) - set(input_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Input data is missing required features: "
            f"{sorted(missing_columns)}"
        )

    result = input_df.copy()

    X = result[FEATURE_COLUMNS]

    predictions = model.predict(X)

    # Demand cannot be negative.
    result["prediction"] = predictions.clip(min=0)

    return result
