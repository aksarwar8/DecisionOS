import time

import pandas as pd
from sqlalchemy import text

from backend.services.analytics_service import _PLATFORM_LATEST
from backend.services.model_service import load_forecasting_model_info
from src.decisionos.config import get_settings
from src.decisionos.data.extract import get_engine
from src.decisionos.data.validate import HistoricalSalesError, validate_historical_sales
from src.decisionos.ml.batch_forecast import forecast_aligned_batch


def resolve_scope(request):
    conditions = []
    params = {}
    for field, column in (("state", "s.state"), ("category", "p.category"), ("department", "p.department")):
        value = getattr(request, field)
        if value is not None:
            params[field] = value
            conditions.append(f"AND {column} = :{field}")
    for field, column in (("product_ids", "p.id"), ("store_ids", "s.id")):
        value = getattr(request, field)
        if value:
            params[field] = value
            conditions.append(f"AND {column} = ANY(:{field})")
    if request.pairs:
        params["pair_products"] = [pair.product_id for pair in request.pairs]
        params["pair_stores"] = [pair.store_id for pair in request.pairs]
        conditions.append("""
            AND EXISTS (SELECT 1 FROM unnest(CAST(:pair_products AS integer[]),
                                             CAST(:pair_stores AS integer[])) AS pair(product_id, store_id)
                        WHERE pair.product_id = p.id AND pair.store_id = s.id)
        """)
    query = text(f"""
        SELECT p.id AS product_id, s.id AS store_id, p.item_id, s.store_id AS store_code,
               p.category, p.department, s.state
        FROM products p CROSS JOIN stores s WHERE TRUE {' '.join(conditions)}
        ORDER BY p.id, s.id
    """)
    with get_engine().connect() as connection:
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        candidates = pd.read_sql(query, connection, params=params)
    if request.pairs:
        requested = {(pair.product_id, pair.store_id) for pair in request.pairs}
        found = set(zip(candidates["product_id"], candidates["store_id"]))
        if requested != found:
            raise HistoricalSalesError("Some requested pairs do not exist or do not match the filters.")
    if request.product_ids and set(request.product_ids) != set(candidates["product_id"]):
        raise HistoricalSalesError("Some requested products do not exist or do not match the filters.")
    if request.store_ids and set(request.store_ids) != set(candidates["store_id"]):
        raise HistoricalSalesError("Some requested stores do not exist or do not match the filters.")
    return candidates


def scope_preview(request, candidates=None):
    candidates = resolve_scope(request) if candidates is None else candidates
    settings = get_settings()
    pair_limit = int(settings.forecast_max_pairs)
    row_limit = int(settings.forecast_max_rows)
    if pair_limit < 1 or row_limit < 1:
        raise RuntimeError("Forecast workload limits must be positive.")
    count = len(candidates)
    return {
        "scope": request, "candidate_pairs": count, "eligible_pairs": None,
        "excluded_pairs": None, "exclusions": [], "estimated_rows": count * request.horizon,
        "max_pairs": pair_limit, "max_rows": row_limit,
        "within_limits": count <= pair_limit and count * request.horizon <= row_limit,
    }


def extract_histories(candidates, origin):
    query = text(f"""
        WITH latest AS MATERIALIZED ({_PLATFORM_LATEST}),
        selected AS (
            SELECT * FROM unnest(CAST(:products AS integer[]), CAST(:stores AS integer[]))
            AS pair(product_id, store_id)
        ), chosen AS (
            SELECT latest_date, COALESCE(CAST(:origin AS date), latest_date) AS origin FROM latest
        )
        SELECT chosen.latest_date, chosen.origin, sales.product_id, sales.store_id,
               calendar.date, sales.sales_quantity
        FROM chosen
        LEFT JOIN (
            selected JOIN sales ON sales.product_id = selected.product_id AND sales.store_id = selected.store_id
            JOIN calendar ON calendar.id = sales.calendar_id
        ) ON calendar.date BETWEEN chosen.origin - 89 AND chosen.origin
           AND chosen.origin <= chosen.latest_date
        ORDER BY sales.product_id, sales.store_id, calendar.date
    """)
    params = {
        "products": candidates["product_id"].tolist(),
        "stores": candidates["store_id"].tolist(), "origin": origin,
    }
    with get_engine().connect() as connection:
        connection.exec_driver_sql("SET LOCAL statement_timeout = '25s'")
        history = pd.read_sql(query, connection, params=params)
    latest = history["latest_date"].iloc[0]
    selected_origin = history["origin"].iloc[0]
    if pd.isna(latest):
        raise HistoricalSalesError("No actual sales date is available.")
    if selected_origin > latest:
        raise HistoricalSalesError("Forecast origin must not be after the latest actual sales date.")
    history = history.dropna(subset=["product_id"]).copy()
    if not history.empty:
        history[["product_id", "store_id"]] = history[["product_id", "store_id"]].astype(int)
        history["date"] = pd.to_datetime(history["date"])
    return history, pd.Timestamp(selected_origin)


def partition_histories(candidates, history, origin):
    groups = {(product, store): group for (product, store), group in
              history.groupby(["product_id", "store_id"], sort=False)}
    accepted = []
    excluded = []
    for row in candidates.itertuples(index=False):
        key = (row.product_id, row.store_id)
        group = groups.get(key)
        reason = None
        if group is None:
            reason = "No observations in the 90-day history window."
        else:
            try:
                validate_historical_sales(group)
                if len(group) < 28:
                    reason = "Fewer than 28 daily observations."
                elif group["date"].max() != origin:
                    reason = "No observation on the common forecast origin."
            except HistoricalSalesError as error:
                reason = str(error)
        if reason:
            excluded.append({"product_id": key[0], "store_id": key[1], "reason": reason})
        else:
            accepted.append(group)
    return (pd.concat(accepted, ignore_index=True) if accepted else history.iloc[0:0]), excluded


def _breakdowns(forecasts, candidates):
    merged = forecasts.merge(candidates, on=["product_id", "store_id"], validate="many_to_one")
    results = []
    for dimension, key, label in (
        ("product", "product_id", "item_id"), ("store", "store_id", "store_code"),
        ("category", "category", "category"), ("department", "department", "department"),
        ("state", "state", "state"),
    ):
        grouped = merged.groupby([key] if key == label else [key, label], dropna=False)["prediction"].sum()
        for group, value in grouped.items():
            identifier, name = (group, group) if key == label else group
            identifier = None if pd.isna(identifier) else identifier
            name = f"Unknown {dimension}" if pd.isna(name) else str(name)
            results.append({"dimension": dimension, "id": identifier, "label": name, "prediction": value})
    return results


def generate_batch(request):
    candidates = resolve_scope(request)
    preview = scope_preview(request, candidates)
    if not preview["within_limits"]:
        raise HistoricalSalesError("Scope exceeds synchronous forecast limits. Narrow the selection.")
    if candidates.empty:
        raise HistoricalSalesError("No catalog pairs match the requested scope.")
    start = time.perf_counter()
    history, origin = extract_histories(candidates, request.origin)
    eligible, exclusions = partition_histories(candidates, history, origin)
    extraction = time.perf_counter() - start
    if eligible.empty:
        details = "; ".join(
            f"{item['product_id']}/{item['store_id']}: {item['reason']}" for item in exclusions
        )
        raise HistoricalSalesError(f"No pairs have sufficient valid history at the common origin. {details}")
    settings = get_settings()
    model, version = load_forecasting_model_info()
    inference_start = time.perf_counter()
    forecast = forecast_aligned_batch(model, eligible, request.horizon)
    inference = time.perf_counter() - inference_start
    daily = forecast.groupby("date", as_index=False)["prediction"].sum()
    eligible_pairs = eligible[["product_id", "store_id"]].drop_duplicates()
    common_start = eligible.groupby(["product_id", "store_id"])["date"].min().max()
    historical = eligible.loc[eligible["date"] >= common_start].groupby(
        "date", as_index=False
    )["sales_quantity"].sum()
    eligible_catalog = candidates.merge(eligible_pairs, on=["product_id", "store_id"], validate="one_to_one")
    return {
        **preview, "eligible_pairs": len(eligible_pairs), "excluded_pairs": len(exclusions),
        "exclusions": exclusions, "coverage": "partial" if exclusions else "complete",
        "origin": origin.date(), "forecast_start": daily["date"].min().date(),
        "forecast_end": daily["date"].max().date(), "model_uri": settings.registered_model_uri,
        "model_version": version, "daily": daily.to_dict("records"),
        "total_prediction": float(daily["prediction"].sum()),
        "historical": historical.rename(columns={"sales_quantity": "demand"}).to_dict("records"),
        "breakdowns": _breakdowns(forecast, eligible_catalog),
        "extraction_seconds": extraction, "inference_seconds": inference,
    }
