"""Quality-metrics pure assembly + repo SQL guards."""
from db import database
from db.repositories import metrics_repo
from services import metrics


# --------------------------- pure rate math ------------------------------
def test_ratio_and_pct_divide_by_zero_safe():
    assert metrics.ratio(5, 0) == 0.0
    assert metrics.pct(5, 0) == 0.0
    assert metrics.ratio(1, 4) == 0.25
    assert metrics.pct(1, 4) == 25.0


def test_build_report_computes_rates():
    raw = {
        "consumer": {
            "total_customers": 100, "customers_with_confirmed": 40,
            "repeat_customers": 4, "booking_started": 50, "confirmed_orders": 45,
            "price_enquiry_customers": 12, "confirmed_revenue": 4500.0,
        },
        "escalations": {"total_conversations": 200, "flagged_conversations": 20,
                        "open_complaints": 3, "pending_tasks_open": 5,
                        "pending_tasks_overdue": 1},
        "by_service": [{"service": "Wash & Fold", "confirmed": 20, "revenue_aed": 1200.0}],
        "by_market": [{"market": "AE", "confirmed": 40}],
        "by_segment": [{"lifecycle_stage": "repeat_customer", "count": 4}],
        "b2b": {"open_leads": 2},
    }
    r = metrics.build_quality_report(raw)
    # Historical benchmark shape: ~40% conversion, ~10% repeat.
    assert r["consumer"]["conversion"]["customer_conversion_rate_pct"] == 40.0
    assert r["consumer"]["repeat_customer_rate_pct"] == 10.0
    assert r["consumer"]["conversion"]["started_to_confirmed_rate_pct"] == 90.0
    assert r["consumer"]["avg_order_value_aed"] == 100.0
    assert r["escalations"]["escalation_rate_pct"] == 10.0
    assert r["b2b"]["open_leads"] == 2
    assert r["by_service"][0]["service"] == "Wash & Fold"


def test_build_report_all_zero_when_empty():
    r = metrics.build_quality_report({})
    assert r["consumer"]["total_customers"] == 0
    assert r["consumer"]["conversion"]["customer_conversion_rate_pct"] == 0.0
    assert r["escalations"]["escalation_rate_pct"] == 0.0
    assert r["by_service"] == []


# --------------------------- repo SQL guards -----------------------------
async def test_consumer_excludes_b2b_and_demo(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        return {"total_customers": 0, "customers_with_confirmed": 0, "repeat_customers": 0,
                "booking_started": 0, "price_enquiry_customers": 0,
                "confirmed_orders": 0, "confirmed_revenue": 0}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await metrics_repo._consumer(False)
    # B2B leads and demo rows are excluded from consumer conversion.
    assert "c.is_b2b = false" in captured["sql"]
    assert "is_demo = false" in captured["sql"]
    # Repeat = 2+ confirmed booking cycles.
    assert "confirmed >= 2" in captured["sql"]


async def test_by_market_excludes_b2b(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await metrics_repo._by_market(False)
    assert "c.is_b2b = false" in captured["sql"]
