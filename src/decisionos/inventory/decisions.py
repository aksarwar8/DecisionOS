"""Deterministic simulated inventory decisions, with explicit arrival timing."""

import math


def order_quantity(desired, minimum, multiple):
    if desired <= 0:
        return 0
    return int(math.ceil(max(desired, minimum) / multiple) * multiple)


def recommend(forecasts, assumptions, order_override=None):
    lead = assumptions["lead_days"]
    if len(forecasts) < lead + 7:
        raise ValueError("The forecast must cover lead time plus seven review days.")
    demand = sum(forecasts[:lead])
    position = assumptions["stock"] + assumptions["incoming"]
    reorder_point = demand + assumptions["safety_stock"]
    target = reorder_point + sum(forecasts[lead:lead + 7])
    quantity = order_quantity(max(0, target - position), assumptions["minimum_order"], assumptions["order_multiple"])         if position <= reorder_point else 0
    if order_override is not None:
        quantity = order_override
    # Incoming inventory is assumed to arrive at the end of the lead time.
    stock = float(assumptions["stock"])
    shortage = 0.0
    projection = []
    for index, value in enumerate(forecasts):
        if index == lead:
            stock += assumptions["incoming"] + quantity
        fulfilled = min(stock, value)
        stock -= fulfilled
        shortage += value - fulfilled
        projection.append({"day": index + 1, "demand": value, "stock": stock,
                           "unfulfilled": value - fulfilled})
    return {"inventory_position": position, "lead_time_demand": demand, "reorder_point": reorder_point,
            "order_up_to": target, "recommended_quantity": quantity,
            "estimated_procurement_cost": quantity * assumptions["unit_cost"],
            "projected_shortage": shortage, "projected_ending_stock": stock,
            "shortage_exposure": shortage * assumptions["shortage_cost"],
            "holding_exposure": sum(p["stock"] for p in projection) * assumptions["holding_cost"],
            "stockout_indicator": shortage > 0,
            "overstock_indicator": position > sum(forecasts) + assumptions["safety_stock"],
            "estimated_fill_rate": (1 - shortage / sum(forecasts)) if sum(forecasts) else None,
            "coverage_days": assumptions["stock"] / (sum(forecasts) / len(forecasts))
            if sum(forecasts) else None,
            "priority": "high" if shortage > 0 else "medium" if quantity else "low",
            "projection": projection}


def allocate(recommendations, budget):
    # Greedy by projected shortage value per procurement unit; not a global optimum.
    remaining = budget
    result = []
    for item in sorted(recommendations, key=lambda x: (-x["priority_score"], x["product_id"], x["store_id"])):
        multiple, minimum, cost = item["order_multiple"], item["minimum_order"], item["unit_cost"]
        allowed = item["quantity"] if cost == 0 else min(item["quantity"], int(remaining // cost))
        allowed = int(allowed // multiple * multiple)
        if allowed < minimum:
            allowed = 0
        spend = allowed * cost
        remaining -= spend
        result.append({"product_id": item["product_id"], "store_id": item["store_id"],
                       "quantity": allowed, "cost": spend})
    return {"allocations": result, "spent": budget - remaining, "remaining": remaining,
            "method": "Greedy projected shortage-cost reduction less holding cost per procurement cost; ties by IDs."}
