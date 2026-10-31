
import pandas as pd


def analyze_weekly_seasonality(daily_total_sales, calendar):
    """Analyze average sales for each weekday."""

    sales_by_day = daily_total_sales.reset_index()

    sales_by_day.columns = ["day", "total_sales"]

    sales_by_day = sales_by_day.merge(
        calendar[["d", "weekday"]].rename(columns={"d": "day"}),
        on="day",
        how="left"
    )

    weekday_sales = (
        sales_by_day.groupby("weekday")["total_sales"]
        .mean()
        .sort_values(ascending=False)
    )

    print("\n--- Average Sales by Weekday ---")
    print(weekday_sales)

    return weekday_sales




def analyze_monthly_seasonality(daily_total_sales, calendar):
    """Analyze average sales for each month."""

    sales_by_day = daily_total_sales.reset_index()

    sales_by_day.columns = ["day", "total_sales"]

    sales_by_day = sales_by_day.merge(
        calendar[["d", "month"]].rename(columns={"d": "day"}),
        on="day",
        how="left"
    )

    monthly_sales = (
        sales_by_day.groupby("month")["total_sales"]
        .mean()
        .sort_index()
    )

    print("\n--- Average Sales by Month ---")
    print(monthly_sales)

    return monthly_sales
