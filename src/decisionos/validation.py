
def validate_m5_data(sales, calendar, prices):
    """Validate the three M5 datasets."""

    errors = []

    # 1. Check empty datasets
    if sales.empty:
        errors.append("Sales dataset is empty.")

    if calendar.empty:
        errors.append("Calendar dataset is empty.")

    if prices.empty:
        errors.append("Prices dataset is empty.")

    # 2. Check required columns
    required_sales = {
        "id", "item_id", "dept_id",
        "cat_id", "store_id", "state_id"
    }

    required_calendar = {
        "date", "wm_yr_wk", "d"
    }

    required_prices = {
        "store_id", "item_id",
        "wm_yr_wk", "sell_price"
    }

    if not required_sales.issubset(sales.columns):
        errors.append("Sales dataset has missing columns.")

    if not required_calendar.issubset(calendar.columns):
        errors.append("Calendar dataset has missing columns.")

    if not required_prices.issubset(prices.columns):
        errors.append("Prices dataset has missing columns.")

    # 3. Check duplicate records
    if sales.duplicated().any():
        errors.append("Duplicate records found in sales.")

    if calendar.duplicated().any():
        errors.append("Duplicate records found in calendar.")

    if prices.duplicated().any():
        errors.append("Duplicate records found in prices.")

    # 4. Final result
    if errors:
        for error in errors:
            print("VALIDATION ERROR:", error)

        return False

    print("All datasets passed validation.")
    return True
