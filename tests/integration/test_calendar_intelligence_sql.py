from datetime import date

import pytest
from sqlalchemy import text

from backend.api.schemas.calendar_intelligence import EventQuery, EventWindowQuery, PriceQuery, SeasonalityQuery, SnapQuery
from backend.services import calendar_intelligence_service as calendar
from backend.services.price_intelligence_service import build_price_statement

pytestmark = pytest.mark.integration


def _execute(connection, statement):
    sql, params = statement
    fixture = f"""
        WITH calendar AS (
            SELECT n AS id, DATE '2021-01-01' + (n - 1) AS date, 1 + (n - 1) / 7 AS wm_yr_wk,
                   CASE WHEN n IN (1, 8) THEN 'Festival' WHEN n = 15 THEN 'Other' END AS event_name_1,
                   CASE WHEN n IN (1, 8, 15) THEN 'Cultural' END AS event_type_1,
                   CASE WHEN n = 1 THEN 'Sport' WHEN n = 8 THEN 'Festival' END AS event_name_2,
                   CASE WHEN n = 1 THEN 'Sporting' WHEN n = 8 THEN 'Cultural' END AS event_type_2,
                   CASE WHEN n = 1 THEN 1 ELSE 0 END AS snap_ca, 0 AS snap_tx,
                   CASE WHEN n = 1 THEN 1 ELSE 0 END AS snap_wi
            FROM generate_series(1, 36) n
        ), products(id,item_id,category,department) AS (
            VALUES (1, 'ITEM_1', 'FOODS', 'FOODS_1'), (2, 'ITEM_2', 'FOODS', 'FOODS_1')
        ), stores(id,store_id,state) AS (
            VALUES (1, 'CA_1', 'CA'), (2, 'TX_1', 'TX'), (3, 'WI_1', 'WI'), (4, 'X_1', NULL)
        ), sales(product_id,store_id,calendar_id,sales_quantity) AS (
            VALUES (1,1,1,1),(2,1,1,3),(1,1,2,0),(1,1,8,8),(1,1,16,7),(1,1,22,2),(1,1,29,0),(1,1,33,6),
                   (1,2,1,10),(1,3,1,2),(1,4,1,5)
        ), sell_prices(product_id,store_id,wm_yr_wk,sell_price) AS (
            VALUES (1,1,1,2.0),(1,1,1,2.0),(1,1,2,3.0),(1,1,4,5.0),(1,1,4,6.0),(1,1,5,4.0),
                   (1,2,1,99.0),(2,1,1,99.0)
        ), {str(sql).strip()[5:]}
    """
    return connection.execute(text(fixture), params).mappings().one()


def test_seasonality_daily_grain_and_unequal_bucket_coverage(connection):
    row = _execute(connection, calendar.build_seasonality_statement(
        SeasonalityQuery(days=33, store_id=1, group_by="weekday"),
    ))
    weekdays = {bucket["label"]: bucket for bucket in row["buckets"]}
    friday = weekdays["Friday"]
    assert friday["total_demand"] == 14 and friday["average_daily_demand"] == 3.5
    assert friday["observed_days"] == 4 and friday["expected_days"] == 5
    assert friday["coverage_pct"] == 80 and friday["zero_demand_days"] == 1
    assert friday["daily_stddev"] == pytest.approx((35 / 3) ** 0.5)
    assert weekdays["Sunday"]["total_demand"] is None
    for grouping in ("month", "year_month"):
        months = _execute(connection, calendar.build_seasonality_statement(
            SeasonalityQuery(days=33, store_id=1, group_by=grouping),
        ))["buckets"]
        assert [(item["expected_days"], item["partial_calendar_period"]) for item in months] == [
            (31, False), (2, True),
        ]
        assert months[1]["average_daily_demand"] == 6
    year = _execute(connection, calendar.build_seasonality_statement(
        SeasonalityQuery(days=33, store_id=1, group_by="year"),
    ))["buckets"][0]
    assert year["partial_calendar_period"] and year["expected_days"] == 33
    weekend = _execute(connection, calendar.build_seasonality_statement(
        SeasonalityQuery(days=33, store_id=1, group_by="weekday_weekend"),
    ))["buckets"][1]
    assert weekend["total_demand"] == 7 and weekend["zero_demand_days"] == 1


def test_event_overlap_uses_distinct_days_and_excludes_other_events_from_baseline(connection):
    query = EventQuery(days=33, store_id=1, event_name="Festival")
    row = _execute(connection, calendar.build_event_statement(query))
    assert row["event"]["expected_days"] == row["event"]["observed_days"] == 2
    assert row["event"]["total_demand"] == 12
    baseline = row["non_event_baseline"]
    assert baseline["expected_days"] == baseline["observed_days"] == 2
    assert baseline["total_demand"] == 2 and baseline["zero_demand_days"] == 1
    comparison = calendar.compare_weekdays(row["weekdays"], row["baseline"])
    assert comparison["standardized_baseline_average"] == 1
    assert comparison["absolute_difference"] == 5


def test_event_offsets_clip_requested_window_and_preserve_observed_zero(connection):
    query = EventWindowQuery(days=33, store_id=1, event_name="Festival", before=1, after=1)
    row = _execute(connection, calendar.build_event_statement(query, relative=True))
    assert row["occurrence_days"] == 2
    offsets = {group["offset"]: group for group in row["statistics"]}
    assert offsets[-1]["expected_days"] == 1 and offsets[-1]["total_demand"] is None
    assert offsets[0]["total_demand"] == 12
    assert offsets[1]["expected_days"] == 2 and offsets[1]["observed_days"] == 1
    assert offsets[1]["total_demand"] == 0


def test_snap_uses_state_specific_flags_after_store_day_aggregation(connection):
    query = SnapQuery(days=1, end_date=date(2021, 1, 1), aggregation="daily")
    row = _execute(connection, calendar.build_snap_statement(query))
    snap, no_snap = row["groups"]
    assert snap["total_demand"] == 6 and snap["observed_store_days"] == 2
    assert snap["average_demand_per_observed_store_day"] == 3
    assert no_snap["total_demand"] == 10 and no_snap["observed_store_days"] == 1
    assert row["excluded_observed_store_days"] == 1


def test_price_weekly_join_ignores_duplicates_and_excludes_conflicts_and_missing_quotes(connection):
    row = _execute(connection, build_price_statement(PriceQuery(days=33, product_id=1, store_id=1)))
    assert row["total_demand"] == 24 and row["matched_demand"] == 15
    assert row["estimated_sales_value"] == 50
    assert float(row["weighted_average_unit_price"]) == pytest.approx(50 / 15)
    assert row["observed_days"] == 7 and row["matched_days"] == 5
    assert float(row["match_coverage_pct"]) == pytest.approx(100 * 5 / 7)
    assert row["weekly"][2]["unit_price"] is None and row["weekly"][2]["total_demand"] == 7
    assert row["weekly"][3]["price_conflict"] and row["weekly"][3]["unit_price"] is None
    assert row["comparable_price_week_pairs"] == 1 and row["price_change_frequency_pct"] == 100
    assert row["changes"][0]["average_daily_demand_difference"] == 7.5
    assert row["correlation_week_count"] == 3


def test_price_correlation_is_undefined_for_one_quote(connection):
    row = _execute(connection, build_price_statement(PriceQuery(days=7, end_date=date(2021, 1, 7),
                                                              product_id=1, store_id=1)))
    assert row["correlation_week_count"] == 1 and row["price_demand_correlation"] is None
    assert row["price_change_frequency_pct"] is None
