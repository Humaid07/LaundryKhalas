"""Facility finance repo + range math tests.

Money math + the date-range mapping are pure and testable; the SQL aggregate is
exercised with a stubbed ``database`` (the ``client`` suite runs on SQLite).
"""
from datetime import date, datetime, timedelta

from api import facility as facility_api
from db import database
from db.repositories import facility_finance_repo as fin


# --------------------------- date-range math (6) --------------------------
def test_range_to_dates_today():
    today = datetime.utcnow().date()
    assert facility_api._range_to_dates("today", None, None) == (today, today)


def test_range_to_dates_week_and_month():
    today = datetime.utcnow().date()
    assert facility_api._range_to_dates("week", None, None) == (today - timedelta(days=6), today)
    assert facility_api._range_to_dates("month", None, None) == (today - timedelta(days=29), today)


def test_range_to_dates_custom_and_all():
    assert facility_api._range_to_dates("custom", "2026-07-01", "2026-07-10") == (
        date(2026, 7, 1), date(2026, 7, 10))
    assert facility_api._range_to_dates(None, None, None) == (None, None)


def test_finance_dates_upper_bound_is_exclusive():
    # finance repo filters `< date_to`, so the API bumps the upper bound by a day
    # to keep the range inclusive of the end date.
    date_from, date_to = facility_api._finance_dates("custom", "2026-07-01", "2026-07-10")
    assert date_from == date(2026, 7, 1)
    assert date_to == date(2026, 7, 11)


# --------------------------- summary money math (6) -----------------------
async def test_summary_computes_average_and_defers_payout(monkeypatch):
    async def fake_fetchrow(sql, *args):
        assert "o.facility_id = $1" in sql
        assert args[0] == "FAC-1"
        return {"order_count": 4, "revenue_total": 200}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await fin.summary("FAC-1", date(2026, 7, 1), date(2026, 7, 31))
    assert out["order_count"] == 4
    assert out["revenue_total"] == 200.0
    assert out["average_order_value"] == 50.0
    assert out["currency"] == "AED"
    # Partner payout is deferred — never invented.
    assert out["payout_status"] == "pending_rate"
    assert out["payout_amount"] is None


async def test_summary_zero_orders_no_divide_by_zero(monkeypatch):
    async def fake_fetchrow(sql, *args):
        return {"order_count": 0, "revenue_total": 0}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await fin.summary("FAC-1", None, None)
    assert out["order_count"] == 0
    assert out["average_order_value"] == 0.0


# --------------------------- service mix shape (7) ------------------------
async def test_service_mix_returns_category_count_value(monkeypatch):
    async def fake_fetch(sql, *args):
        assert "o.facility_id = $1" in sql
        return [
            {"category": "Everyday", "count": 3, "value": 90},
            {"category": "Premium", "count": 1, "value": 60},
        ]

    monkeypatch.setattr(database, "fetch", fake_fetch)
    out = await fin.service_mix("FAC-1", None, None)
    assert out == [
        {"category": "Everyday", "count": 3, "value": 90.0},
        {"category": "Premium", "count": 1, "value": 60.0},
    ]
    assert all({"category", "count", "value"} == set(row) for row in out)


async def test_revenue_timeseries_shape(monkeypatch):
    async def fake_fetch(sql, *args):
        assert "date_trunc('day'" in sql
        return [{"period": "2026-07-01", "count": 2, "value": 40}]

    monkeypatch.setattr(database, "fetch", fake_fetch)
    out = await fin.revenue_timeseries("FAC-1", "day", None, None)
    assert out == [{"period": "2026-07-01", "count": 2, "value": 40.0}]
