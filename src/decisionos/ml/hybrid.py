
import numpy as np
import pandas as pd

from src.decisionos.ml.forecast import recursive_forecast
from src.decisionos.ml.demand_segments import DEMAND_SEGMENTS, DEMAND_SEGMENT_UPPER_BOUNDS


MODEL_SELECTION = {
    "Zero average": "Historical Mean",
    "Low demand": "Random Forest",
    "Medium demand": "Random Forest",
    "High demand": "Random Forest",
}


def hybrid_forecast(
    model,
    history_df: pd.DataFrame,
    future_dates: list,
) -> pd.DataFrame:
    """
    Generate forecasts using validation-selected models
    for each historical demand segment.

    Demand segments and historical means are calculated
    using historical data only.
    """

    # Generate recursive Random Forest forecasts.
    rf_forecasts = recursive_forecast(
        model=model,
        history_df=history_df,
        future_dates=future_dates,
    )

    # Calculate historical average demand per product-store pair.
    historical_stats = (
        history_df.groupby(
            ["product_id", "store_id"]
        )["sales_quantity"]
        .mean()
        .reset_index(name="historical_average")
    )

    # Assign demand segments.
    historical_stats["demand_segment"] = pd.cut(
        historical_stats["historical_average"],
        bins=[-np.inf, *DEMAND_SEGMENT_UPPER_BOUNDS, np.inf],
        labels=DEMAND_SEGMENTS,
    )

    # Attach historical means and segment information.
    result = rf_forecasts.merge(
        historical_stats,
        on=["product_id", "store_id"],
        how="left",
        validate="many_to_one",
    )

    # Apply the validation-selected model for each segment.
    result["selected_model"] = (
        result["demand_segment"]
        .astype(str)
        .map(MODEL_SELECTION)
    )

    result["prediction"] = np.where(
        result["selected_model"] == "Historical Mean",
        result["historical_average"],
        result["prediction"],
    )

    result["prediction"] = result["prediction"].clip(lower=0)

    return result[
        [
            "product_id",
            "store_id",
            "date",
            "demand_segment",
            "selected_model",
            "prediction",
        ]
    ]
