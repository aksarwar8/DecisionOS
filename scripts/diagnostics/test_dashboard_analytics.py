if __name__ == "__main__":

    from dashboard.api_client import (
        get_product_analytics,
        get_store_analytics,
        get_demand_trends,
    )


    print("\nPRODUCT ANALYTICS")

    product = get_product_analytics(4)

    print(product)


    print("\nSTORE ANALYTICS")

    store = get_store_analytics(1)

    print(store)


    print("\nDEMAND TRENDS")

    trend = get_demand_trends(
        product_id=4,
        store_id=1,
    )

    print("Number of records:", len(trend["trend"]))
    print("Total demand:", trend["total_demand"])
    print("Average daily demand:", trend["average_daily_demand"])
