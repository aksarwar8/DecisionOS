
from decisionos.ingestion import load_m5_data
from decisionos.validation import validate_m5_data
from decisionos.preprocessing import (
    preprocess_calendar,
    save_processed_data,
)

from decisionos.aggregation import aggregate_product_sales
from decisionos.preprocessing import save_product_sales


def run_pipeline():
    """Execute the complete DecisionOS data pipeline."""

    print("=" * 45)
    print("DecisionOS: Data Pipeline Started")
    print("=" * 45)

    # Step 1: Ingestion
    print("\n[1/6] Loading raw M5 datasets...")

    sales, calendar, prices = load_m5_data()

    print(f"Sales: {sales.shape}")
    print(f"Calendar: {calendar.shape}")
    print(f"Prices: {prices.shape}")

    # Step 2: Validation
    print("\n[2/6] Validating datasets...")

    is_valid = validate_m5_data(sales, calendar, prices)

    if not is_valid:
        raise ValueError("Pipeline stopped: validation failed.")

    # Step 3: Preprocessing
    print("\n[3/6] Preprocessing calendar data...")

    calendar = preprocess_calendar(calendar)

    print("Calendar preprocessing completed.")


    print("\n[4/6] Aggregating sales at product level...")
    product_sales = aggregate_product_sales(sales)

    print(f"Product-level sales shape: {product_sales.shape}")

    print("\n[5/6] Saving product-level sales...")
    save_product_sales(product_sales)

    # Step 4: Save processed data
    print("\n[6/6] Saving datasets as Parquet...")

    save_processed_data(sales, calendar, prices)

    print("\nDecisionOS pipeline completed successfully!")

    return sales, calendar, prices


if __name__ == "__main__":
    run_pipeline()
