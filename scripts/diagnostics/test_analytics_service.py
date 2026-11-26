if __name__ == "__main__":

    from backend.services.analytics_service import (
        get_product_summary,
        get_store_summary,
        get_product_store_trend,
    )


    PRODUCT_ID = 4
    STORE_ID = 1


    print("\n========== PRODUCT SUMMARY ==========")

    product = get_product_summary(
        product_id=PRODUCT_ID,
        days=90,
    )

    for key, value in product.items():
        print(f"{key}: {value}")


    print("\n========== STORE SUMMARY ==========")

    store = get_store_summary(
        store_id=STORE_ID,
        days=90,
    )

    for key, value in store.items():
        print(f"{key}: {value}")


    print("\n========== HISTORICAL DEMAND TREND ==========")

    trend = get_product_store_trend(
        product_id=PRODUCT_ID,
        store_id=STORE_ID,
        days=90,
    )

    print(trend.tail(10).to_string(index=False))

    print("\nTrend statistics:")
    print("Rows:", len(trend))
    print("Total demand:", trend["sales_quantity"].sum())
    print("Average daily demand:", trend["sales_quantity"].mean())
