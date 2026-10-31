
import pandas as pd


def analyze_product_sales(product_sales):
    """Analyze aggregated product-level sales."""

    day_columns = [
        col for col in product_sales.columns
        if col.startswith("d_")
    ]

    daily_sales = product_sales[day_columns]

    print("\n--- Product Sales Analysis ---")

    print(f"Total products: {len(product_sales)}")
    print(f"Total days: {len(day_columns)}")

    print(f"Total units sold: {daily_sales.sum().sum():,.0f}")

    print(f"Average daily sales: {daily_sales.sum(axis=0).mean():,.2f}")

    print("\n--- Product Demand Statistics ---")

    product_totals = daily_sales.sum(axis=1)

    print(f"Average sales per product: {product_totals.mean():,.2f}")
    print(f"Highest product sales: {product_totals.max():,.0f}")
    print(f"Lowest product sales: {product_totals.min():,.0f}")

    return daily_sales
