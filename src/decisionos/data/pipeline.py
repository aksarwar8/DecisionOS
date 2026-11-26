
from src.decisionos.data.extract import extract_sales
from src.decisionos.data.validate import validate_dataframe
from src.decisionos.data.transform import transform_sales


def build_sales_dataset(
    start_date: str,
    end_date: str,
):
    """
    Build a validated and transformed sales dataset.

    Workflow:
        1. Extract sales from PostgreSQL.
        2. Validate the extracted data.
        3. Transform sales and create calendar features.
        4. Return the final DataFrame.
    """

    # Step 1: Extract
    sales_df = extract_sales(
        start_date=start_date,
        end_date=end_date,
    )

    # Step 2: Validate
    validate_dataframe(
        sales_df,
        required_columns=[
            "product_id",
            "store_id",
            "date",
            "sales_quantity",
        ],
        name="Extracted Sales",
    )

    # Step 3: Transform
    transformed_df = transform_sales(sales_df)

    # Step 4: Validate transformed dataset
    validate_dataframe(
        transformed_df,
        required_columns=[
            "product_id",
            "store_id",
            "date",
            "sales_quantity",
            "year",
            "month",
            "day",
            "day_of_week",
            "week_of_year",
        ],
        name="Transformed Sales",
    )

    return transformed_df
