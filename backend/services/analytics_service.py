
import pandas as pd

from sqlalchemy import text

from src.decisionos.data.extract import get_engine


class AnalyticsNotFoundError(ValueError):
    """The requested entity or actual-sales period is unavailable."""


# For chronological calendar IDs, each pair's latest sale is one backward
# lookup on the existing (product_id, store_id, calendar_id) index. The CASE
# preserves date semantics if a different calendar load assigns IDs out of order.
_PLATFORM_LATEST = """
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM (
            SELECT date, lag(date) OVER (ORDER BY id) AS previous_date
            FROM calendar
        ) ordered_calendar WHERE date <= previous_date
    ) THEN (
        SELECT c.date FROM calendar c WHERE c.id = (
            SELECT MAX(last_sale.calendar_id)
            FROM products p CROSS JOIN stores st
            CROSS JOIN LATERAL (
                SELECT s.calendar_id FROM sales s
                WHERE s.product_id = p.id AND s.store_id = st.id
                ORDER BY s.calendar_id DESC LIMIT 1
            ) last_sale
        )
    ) ELSE (
        SELECT MAX(c.date) FROM sales s JOIN calendar c ON c.id = s.calendar_id
    ) END AS latest_date
"""


def summarize_period(latest_date, days, total, observed_days, positive_days):
    """Compute inclusive period metadata and demand with explicit denominators."""
    if pd.isna(latest_date):
        raise AnalyticsNotFoundError("No platform sales data found.")
    end = pd.Timestamp(latest_date).date()
    return {
        "period_start": end - pd.Timedelta(days=days - 1),
        "period_end": end,
        "period_days": days,
        "observed_days": int(observed_days),
        "positive_sales_days": int(positive_days),
        "average_daily_demand": float(total) / days,
        "average_observed_day_demand": float(total) / observed_days if observed_days else None,
    }


def _summarize_entity(result, days, missing_message):
    if result.empty:
        raise AnalyticsNotFoundError(missing_message)
    row = result.iloc[0].to_dict()
    period = summarize_period(
        row.pop("latest_date"), days, row["total_sales"],
        row["active_days"], row.pop("positive_days"),
    )
    return {**row, **period}


def get_product_summary(
    product_id: int,
    days: int = 90,
) -> dict:
    """Return product metadata and recent demand statistics."""

    if product_id <= 0 or days < 1:
        raise ValueError("Invalid product_id or days.")

    query = text(f"""
        WITH latest AS ({_PLATFORM_LATEST}),
        daily_sales AS (
            SELECT
                s.product_id,
                c.date,
                SUM(s.sales_quantity) AS daily_demand
            FROM sales s
            JOIN calendar c ON c.id = s.calendar_id
            CROSS JOIN latest
            WHERE s.product_id = :product_id
              AND c.date BETWEEN
                  latest.latest_date - (:days - 1) * INTERVAL '1 day'
                  AND latest.latest_date
            GROUP BY s.product_id, c.date
        )
        SELECT
            p.id AS product_id,
            p.item_id,
            p.category,
            p.department,
            COALESCE(SUM(d.daily_demand), 0) AS total_sales,
            COALESCE(MAX(d.daily_demand), 0) AS maximum_daily_demand,
            MAX(latest.latest_date) AS latest_date,
            COUNT(d.date) AS active_days,
            COUNT(d.date) FILTER (WHERE d.daily_demand > 0) AS positive_days
        FROM products p
        LEFT JOIN latest ON TRUE
        LEFT JOIN daily_sales d ON d.product_id = p.id
        WHERE p.id = :product_id
        GROUP BY p.id, p.item_id, p.category, p.department
    """)

    with get_engine().connect() as connection:
        result = pd.read_sql(
            query,
            connection,
            params={"product_id": product_id, "days": days},
        )

    return _summarize_entity(result, days, f"Product {product_id} not found.")


def get_store_summary(
    store_id: int,
    days: int = 90,
) -> dict:
    """Return store metadata and recent demand statistics."""

    if store_id <= 0 or days < 1:
        raise ValueError("Invalid store_id or days.")

    query = text(f"""
        WITH latest AS ({_PLATFORM_LATEST}),
        daily_sales AS (
            SELECT
                s.store_id,
                c.date,
                SUM(s.sales_quantity) AS daily_demand
            FROM sales s
            JOIN calendar c ON c.id = s.calendar_id
            CROSS JOIN latest
            WHERE s.store_id = :store_id
              AND c.date BETWEEN
                  latest.latest_date - (:days - 1) * INTERVAL '1 day'
                  AND latest.latest_date
            GROUP BY s.store_id, c.date
        )
        SELECT
            st.id AS store_id,
            st.store_id AS store_code,
            st.state,
            COALESCE(SUM(d.daily_demand), 0) AS total_sales,
            COALESCE(MAX(d.daily_demand), 0) AS maximum_daily_demand,
            MAX(latest.latest_date) AS latest_date,
            COUNT(d.date) AS active_days,
            COUNT(d.date) FILTER (WHERE d.daily_demand > 0) AS positive_days
        FROM stores st
        LEFT JOIN latest ON TRUE
        LEFT JOIN daily_sales d ON d.store_id = st.id
        WHERE st.id = :store_id
        GROUP BY st.id, st.store_id, st.state
    """)

    with get_engine().connect() as connection:
        result = pd.read_sql(
            query,
            connection,
            params={"store_id": store_id, "days": days},
        )

    return _summarize_entity(result, days, f"Store {store_id} not found.")


def get_product_store_trend(
    product_id: int,
    store_id: int,
    days: int = 90,
) -> pd.DataFrame:
    """Return daily demand for a product-store combination."""

    if product_id <= 0 or store_id <= 0 or days < 1:
        raise ValueError("Invalid product_id, store_id or days.")

    query = text("""
        WITH latest AS (
            SELECT MAX(c.date) AS latest_date
            FROM sales s
            JOIN calendar c ON c.id = s.calendar_id
            WHERE s.product_id = :product_id
              AND s.store_id = :store_id
        )
        SELECT
            c.date,
            SUM(s.sales_quantity) AS sales_quantity
        FROM sales s
        JOIN calendar c ON c.id = s.calendar_id
        CROSS JOIN latest
        WHERE s.product_id = :product_id
          AND s.store_id = :store_id
          AND c.date BETWEEN
              latest.latest_date - (:days - 1) * INTERVAL '1 day'
              AND latest.latest_date
        GROUP BY c.date
        ORDER BY c.date
    """)

    with get_engine().connect() as connection:
        result = pd.read_sql(
            query,
            connection,
            params={
                "product_id": product_id,
                "store_id": store_id,
                "days": days,
            },
        )

    if result.empty:
        raise AnalyticsNotFoundError(
            f"No sales history found for product {product_id}, "
            f"store {store_id}."
        )

    result["date"] = pd.to_datetime(result["date"])

    return result



def get_platform_overview(days: int = 90) -> dict:
    """
    Return platform-wide demand statistics for the latest
    available sales period.
    """

    if days < 1 or days > 365:
        raise ValueError("Days must be between 1 and 365.")

    query = text(f"""
        WITH latest AS MATERIALIZED ({_PLATFORM_LATEST}),
        period_totals AS (
            SELECT
                s.product_id,
                s.store_id,
                c.date,
                SUM(s.sales_quantity) AS demand
            FROM sales s
            JOIN calendar c ON c.id = s.calendar_id
            CROSS JOIN latest
            WHERE c.date BETWEEN
                latest.latest_date - (:days - 1) * INTERVAL '1 day'
                AND latest.latest_date
            GROUP BY GROUPING SETS ((c.date), (s.product_id), (s.store_id))
        )
        SELECT
            MAX(date) AS latest_sales_date,
            COALESCE(SUM(demand) FILTER (WHERE date IS NOT NULL), 0) AS total_demand,
            COUNT(product_id) AS active_products,
            COUNT(store_id) AS active_stores,
            COUNT(date) AS sales_days,
            COUNT(date) FILTER (WHERE demand > 0) AS positive_days
        FROM period_totals
    """)

    with get_engine().connect() as connection:
        result = pd.read_sql(
            query,
            connection,
            params={"days": days},
        )

    if result.empty:
        raise AnalyticsNotFoundError("No platform sales data found.")

    row = result.iloc[0]
    total = int(row["total_demand"])
    period = summarize_period(
        row["latest_sales_date"], days, total, row["sales_days"], row["positive_days"],
    )
    return {
        **period,
        "latest_sales_date": period["period_end"],
        "total_demand": total,
        "active_products": int(row["active_products"]),
        "active_stores": int(row["active_stores"]),
        "sales_days": period["observed_days"],
    }
