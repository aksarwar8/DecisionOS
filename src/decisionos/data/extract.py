
import pandas as pd
from sqlalchemy import create_engine


from src.decisionos.config import get_settings


def get_engine():
    """Create a SQLAlchemy engine for the DecisionOS database."""
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    return create_engine(database_url)


def extract_calendar():
    """Extract the complete calendar table from PostgreSQL."""
    engine = get_engine()

    query = """
        SELECT *
        FROM calendar
        ORDER BY date
    """

    return pd.read_sql(query, engine)


def extract_prices():
    """Extract selling prices from PostgreSQL."""
    engine = get_engine()

    query = """
        SELECT product_id, store_id, wm_yr_wk, sell_price
        FROM sell_prices
        ORDER BY product_id, store_id, wm_yr_wk
    """

    return pd.read_sql(query, engine)


def extract_sales(start_date=None, end_date=None):
    """Extract sales data with actual dates from PostgreSQL."""

    if start_date is None and end_date is None:
        raise ValueError(
            "Date filtering is required to extract sales data safely."
        )

    if (start_date is None) != (end_date is None):
        raise ValueError("Provide both start_date and end_date.")

    engine = get_engine()

    query = """
        SELECT
            s.product_id,
            s.store_id,
            c.date,
            s.sales_quantity
        FROM sales AS s
        JOIN calendar AS c
            ON s.calendar_id = c.id
        WHERE c.date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY c.date, s.store_id, s.product_id
    """

    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    return pd.read_sql(query, engine, params=params)
