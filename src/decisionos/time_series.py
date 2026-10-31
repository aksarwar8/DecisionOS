
import pandas as pd


def convert_to_long_format(product_sales, calendar):
    day_columns = [
        col for col in product_sales.columns
        if col.startswith("d_")
    ]

    sales_long = product_sales.melt(
        id_vars=[
            "item_id",
            "cat_id",
            "dept_id",
            "store_id"
        ],
        value_vars=day_columns,
        var_name="day",
        value_name="units_sold"
    )

    sales_long = sales_long.merge(
        calendar[["d", "date"]].rename(
            columns={"d": "day"}
        ),
        on="day",
        how="left"
    )

    return sales_long
