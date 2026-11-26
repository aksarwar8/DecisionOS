from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from backend.api.schemas.analytics import OverviewResponse
from backend.services import analytics_service


def test_overview_period_counts_and_denominators(monkeypatch):
    monkeypatch.setattr(analytics_service, "get_engine", MagicMock())
    monkeypatch.setattr(pd, "read_sql", lambda *args, **kwargs: pd.DataFrame([{
        "latest_sales_date": date(2021, 1, 3), "total_demand": 12,
        "sales_days": 2, "positive_days": 1, "active_products": 1, "active_stores": 1,
    }]))
    summary = OverviewResponse.model_validate(analytics_service.get_platform_overview(4))
    assert summary.period_start == date(2020, 12, 31)
    assert summary.period_end == summary.latest_sales_date == date(2021, 1, 3)
    assert summary.period_days == 4
    assert summary.observed_days == summary.sales_days == 2
    assert summary.positive_sales_days == 1
    assert summary.average_daily_demand == 3
    assert summary.average_observed_day_demand == 6


def test_overview_aggregate_without_observations(monkeypatch):
    monkeypatch.setattr(analytics_service, "get_engine", MagicMock())
    monkeypatch.setattr(pd, "read_sql", lambda *args, **kwargs: pd.DataFrame([{
        "latest_sales_date": None, "total_demand": 0, "sales_days": 0, "positive_days": 0,
    }]))
    with pytest.raises(analytics_service.AnalyticsNotFoundError, match="No platform sales"):
        analytics_service.get_platform_overview()


def test_product_with_no_observed_days_still_uses_platform_window(monkeypatch):
    monkeypatch.setattr(analytics_service, "get_engine", MagicMock())
    monkeypatch.setattr(pd, "read_sql", lambda *args, **kwargs: pd.DataFrame([{
        "product_id": 3, "latest_date": date(2021, 1, 3), "total_sales": 0,
        "active_days": 0, "positive_days": 0,
    }]))
    summary = analytics_service.get_product_summary(3, 7)
    assert summary["active_days"] == summary["observed_days"] == 0
    assert summary["average_daily_demand"] == 0
    assert summary["average_observed_day_demand"] is None
    assert summary["period_start"] == date(2020, 12, 28)
