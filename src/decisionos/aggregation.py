
import pandas as pd


def aggregate_product_sales(sales):
    id_columns = ["item_id", "cat_id", "dept_id", "store_id"]

    day_columns = [
        col for col in sales.columns
        if col.startswith("d_")
    ]

    product_store_sales = (
        sales.groupby(id_columns)[day_columns]
        .sum()
        .reset_index()
    )

    return product_store_sales
