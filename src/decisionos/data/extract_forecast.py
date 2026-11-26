
import pandas as pd

from sqlalchemy import text

from src.decisionos.data.extract import get_engine
from src.decisionos.data.validate import HistoricalSalesError


def extract_product_store_history(
    product_id: int,
    store_id: int,
    lookback_days: int = 90,
) -> pd.DataFrame:
    """
    Extract the latest historical sales for one product-store pair.

    The lookback window is measured in calendar days and ends
    on the latest available sales date for that pair.
    """

    if product_id <= 0 or store_id <= 0:
        raise HistoricalSalesError(
            "product_id and store_id must be positive integers."
        )

    if lookback_days < 28:
        raise HistoricalSalesError(
            "lookback_days must be at least 28."
        )

    query = text("""
        WITH latest AS (
            SELECT MAX(c.date) AS latest_date
            FROM sales AS s
            JOIN calendar AS c
                ON s.calendar_id = c.id
            WHERE s.product_id = :product_id
              AND s.store_id = :store_id
        )

        SELECT
            s.product_id,
            s.store_id,
            c.date,
            s.sales_quantity

        FROM sales AS s

        JOIN calendar AS c
            ON s.calendar_id = c.id

        CROSS JOIN latest

        WHERE s.product_id = :product_id
          AND s.store_id = :store_id
          AND c.date BETWEEN
              latest.latest_date - (:lookback_days - 1) * INTERVAL '1 day'
              AND latest.latest_date

        ORDER BY c.date
    """)

    params = {
        "product_id": product_id,
        "store_id": store_id,
        "lookback_days": lookback_days,
    }

    engine = get_engine()

    with engine.connect() as connection:
        history_df = pd.read_sql(
            query,
            connection,
            params=params,
        )

    if history_df.empty:
        raise HistoricalSalesError(
            f"No sales history found for product {product_id} "
            f"and store {store_id}."
        )

    history_df["date"] = pd.to_datetime(
        history_df["date"]
    )

    return history_df
