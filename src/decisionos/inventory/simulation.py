"""Bounded historical lost-sales simulation with past-only moving-average forecasts."""

import numpy as np

from src.decisionos.data.validate import validate_historical_sales
from src.decisionos.inventory.decisions import order_quantity


def simulate(history, assumptions, policy, warmup=28):
    history = history.assign(date=validate_historical_sales(history)).sort_values("date")
    if history[["product_id", "store_id"]].drop_duplicates().shape[0] != 1 or len(history) <= warmup:
        raise ValueError("One product-store history with more than 28 days is required.")
    if policy not in ("none", "fixed", "reorder", "forecast", "budget"):
        raise ValueError("Unknown policy.")
    values = history.sales_quantity.to_numpy(dtype=float)
    stock = float(assumptions["stock"])
    arrivals = {assumptions["lead_days"]: float(assumptions["incoming"])}
    holding = shortage_cost = lost_total = ordered = fulfilled_total = demand_total = 0.0
    stockout_days = 0
    trace = []
    for day in range(warmup, len(values)):
        relative = day - warmup
        stock += arrivals.pop(relative, 0)
        past = values[day-warmup:day]
        daily = float(np.mean(past))
        position = stock + sum(arrivals.values())
        trigger = daily * assumptions["lead_days"] + assumptions["safety_stock"]
        quantity = 0
        if policy == "fixed" and position <= trigger:
            quantity = order_quantity(assumptions["fixed_order"], assumptions["minimum_order"], assumptions["order_multiple"])
        elif policy == "reorder" and position <= trigger:
            quantity = order_quantity(max(0, trigger * 2 - position), assumptions["minimum_order"], assumptions["order_multiple"])
        elif policy in ("forecast", "budget") and position <= trigger:
            quantity = order_quantity(max(0, daily * (assumptions["lead_days"] + 7)
                                          + assumptions["safety_stock"] - position),
                                      assumptions["minimum_order"], assumptions["order_multiple"])
            if policy == "budget" and assumptions["unit_cost"] > 0:
                remaining = max(0, assumptions["simulation_budget"] - ordered * assumptions["unit_cost"])
                quantity = min(quantity, int(remaining // assumptions["unit_cost"]))
                quantity = int(quantity // assumptions["order_multiple"] * assumptions["order_multiple"])
                if quantity < assumptions["minimum_order"]:
                    quantity = 0
        if quantity:
            arrivals[relative + assumptions["lead_days"]] = arrivals.get(relative + assumptions["lead_days"], 0) + quantity
            ordered += quantity
        actual = values[day]
        fulfilled = min(stock, actual)
        lost = actual - fulfilled
        stock -= fulfilled
        demand_total += actual
        fulfilled_total += fulfilled
        lost_total += lost
        stockout_days += int(lost > 0)
        holding += stock * assumptions["holding_cost"]
        shortage_cost += lost * assumptions["shortage_cost"]
        trace.append({"date": history.date.iloc[day].date().isoformat(), "stock": stock, "demand": actual,
                      "unfulfilled": lost, "order": quantity, "forecast_daily": daily})
    procurement = ordered * assumptions["unit_cost"]
    return {"policy": policy, "fill_rate": fulfilled_total / demand_total if demand_total else None,
            "stockout_days": stockout_days, "unfulfilled_demand": lost_total,
            "average_inventory": float(np.mean([item["stock"] for item in trace])),
            "replenishment_quantity": ordered, "holding_cost": holding, "shortage_cost": shortage_cost,
            "procurement_cost": procurement, "total_relevant_cost": holding + shortage_cost + procurement,
            "trace": trace}
