"""Facility rate → customer price (margin) + lowest-cost selection (pure) + repo guards."""
from decimal import Decimal

from db import database
from db.repositories import facility_pricing_repo
from services import facility_pricing


# --------------------------- margin math ---------------------------------
def test_apply_percentage_margin():
    # 30 cost + 40% margin = 42.00
    assert facility_pricing.apply_margin(30, {"margin_type": "percentage", "margin_value": 40}) == Decimal("42.00")


def test_apply_fixed_margin():
    assert facility_pricing.apply_margin(30, {"margin_type": "fixed", "margin_value": 15}) == Decimal("45.00")


def test_margin_is_decimal_rounded():
    out = facility_pricing.apply_margin("6.00", {"margin_type": "percentage", "margin_value": 40})
    assert out == Decimal("8.40")


# --------------------------- geo -----------------------------------------
def test_haversine_none_when_missing_coord():
    assert facility_pricing.haversine_km(None, 55.0, 25.0, 55.0) is None


def test_haversine_marina_to_auh_roughly():
    d = facility_pricing.haversine_km(25.0805, 55.1403, 24.4539, 54.3773)
    assert 90 < d < 130  # Dubai Marina ↔ Abu Dhabi ~100+ km


# --------------------------- lowest selection ----------------------------
def test_pick_lowest_by_rate():
    c = facility_pricing.pick_lowest([
        {"facility_code": "A", "rate": 30}, {"facility_code": "B", "rate": 28}])
    assert c["facility_code"] == "B"


def test_pick_lowest_distance_tiebreak():
    c = facility_pricing.pick_lowest([
        {"facility_code": "A", "rate": 30, "distance_km": 40},
        {"facility_code": "B", "rate": 30, "distance_km": 10}])
    assert c["facility_code"] == "B"


def test_customer_quote_hides_cost_and_margin():
    q = facility_pricing.customer_quote(
        {"facility_id": "f1", "facility_code": "A", "rate": 30, "currency": "AED"},
        {"margin_type": "percentage", "margin_value": 40})
    assert q["customer_price_aed"] == 42.0
    # Cost + margin never present in the customer quote.
    assert "rate" not in q and "cost" not in q and "margin_value" not in q and "margin" not in q


# --------------------------- repo guards ---------------------------------
async def test_candidates_filters_offered_active_accepts(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await facility_pricing_repo.candidates_for_service("CLEAN_PRESS", market="AE")
    sql = captured["sql"]
    assert "fs.offered = true" in sql
    assert "f.accepts_orders = true" in sql
    assert "r.active = true" in sql
    assert "operating_status not in ('closed','paused')" in sql


async def test_margin_rule_precedence_prefers_bespoke(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["args"] = args
        return {"code": "BESPOKE-55", "margin_type": "percentage", "margin_value": 55}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    rule = await facility_pricing_repo.get_margin_rule(bespoke=True, service_code="SHOE_CARE")
    assert rule["code"] == "BESPOKE-55"
    assert captured["args"][0] is True  # bespoke flag passed
