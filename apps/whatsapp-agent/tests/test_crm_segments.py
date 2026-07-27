"""Deterministic CRM segment/lifecycle/funnel engine tests (pure, no DB).

Boundary-driven: exercises each threshold from an explicit test config so the
rules are pinned regardless of the shipped config values, plus one test that the
real config/crm_segments.json loads and drives the engine.
"""
from decimal import Decimal

from services import crm_segments
from services.crm_segments import CustomerFacts, evaluate

# Explicit config so thresholds are pinned in-test (independent of shipped JSON).
CFG = {
    "thresholds": {
        "repeat_min_confirmed_orders": 2,
        "high_value_lifetime_value": 500.0,
        "price_sensitive_min_discount_requests": 2,
        "price_sensitive_min_price_enquiries": 3,
        "inactive_days": 60,
        "campaign_attribution_days": 30,
    }
}


def seg(**kw):
    return evaluate(CustomerFacts(**kw), CFG)


# --------------------------- lifecycle precedence -------------------------
def test_brand_new_contact_is_lead():
    r = seg()
    assert r.lifecycle_stage == "lead"
    assert r.funnel_stage == "NEW_ENQUIRY"
    assert r.segments == []


def test_one_confirmed_is_active_new_customer():
    r = seg(confirmed_order_count=1, lifetime_value=Decimal("60"))
    assert r.lifecycle_stage == "active_customer"
    assert "new_customer" in r.segments
    assert "repeat_customer" not in r.segments
    assert r.funnel_stage == "BOOKING_CONFIRMED"


def test_two_confirmed_is_repeat():
    r = seg(confirmed_order_count=2)
    assert r.lifecycle_stage == "repeat_customer"
    assert "repeat_customer" in r.segments
    assert "new_customer" not in r.segments


def test_complaint_open_beats_repeat_in_lifecycle():
    r = seg(confirmed_order_count=5, has_open_complaint=True)
    assert r.lifecycle_stage == "complaint_open"
    # ...but repeat_customer is still a descriptive segment tag.
    assert "repeat_customer" in r.segments
    assert "complaint_open" in r.segments


def test_b2b_beats_everything_in_lifecycle():
    r = seg(confirmed_order_count=5, has_open_complaint=True, is_b2b=True)
    assert r.lifecycle_stage == "b2b_lead"
    assert "b2b_lead" in r.segments


# --------------------------- segment thresholds --------------------------
def test_high_value_boundary():
    assert "high_value" not in seg(confirmed_order_count=1, lifetime_value=Decimal("499.99")).segments
    assert "high_value" in seg(confirmed_order_count=1, lifetime_value=Decimal("500")).segments


def test_price_sensitive_via_discount_requests():
    assert "price_sensitive" not in seg(discount_request_count=1).segments
    assert "price_sensitive" in seg(discount_request_count=2).segments


def test_price_sensitive_via_enquiries_only_when_no_booking():
    # 3 price enquiries but no booking → price_sensitive.
    assert "price_sensitive" in seg(confirmed_order_count=0, price_enquiry_count=3).segments
    # Same enquiries but they DID book → not price-sensitive on the enquiry rule.
    assert "price_sensitive" not in seg(confirmed_order_count=1, price_enquiry_count=3).segments


def test_bespoke_segment():
    assert "bespoke" in seg(has_bespoke=True).segments


def test_campaign_responder_segment():
    assert "campaign_responder" in seg(campaign_responder=True).segments


# --------------------------- inactivity ----------------------------------
def test_inactive_requires_activity_and_threshold():
    # No prior activity → never "inactive".
    assert "inactive" not in seg(days_since_activity=200).segments
    # Active but recent → not inactive.
    assert "inactive" not in seg(has_any_activity=True, days_since_activity=59).segments
    # Active but stale → inactive.
    assert "inactive" in seg(has_any_activity=True, days_since_activity=60).segments


def test_inactive_lead_lifecycle():
    r = seg(has_any_activity=True, days_since_activity=90)  # 0 confirmed, gone cold
    assert r.lifecycle_stage == "inactive"


# --------------------------- funnel stage --------------------------------
def test_funnel_started_when_draft_no_confirm():
    assert seg(has_active_draft=True).funnel_stage == "BOOKING_STARTED"


def test_funnel_price_enquiry():
    assert seg(price_enquiry_count=1).funnel_stage == "PRICE_ENQUIRY"


def test_funnel_confirmed_wins_over_draft():
    assert seg(confirmed_order_count=1, has_active_draft=True).funnel_stage == "BOOKING_CONFIRMED"


# --------------------------- determinism + config ------------------------
def test_segments_order_is_deterministic():
    r = seg(confirmed_order_count=2, lifetime_value=Decimal("900"),
            discount_request_count=3, has_bespoke=True)
    # Canonical order: repeat_customer, high_value, price_sensitive, bespoke.
    assert r.segments == ["repeat_customer", "high_value", "price_sensitive", "bespoke"]


def test_shipped_config_loads_and_drives_engine():
    cfg = crm_segments._load_config()
    assert "thresholds" in cfg
    r = evaluate(CustomerFacts(confirmed_order_count=2))  # default config path
    assert r.lifecycle_stage == "repeat_customer"


def test_money_coercion_is_decimal_safe():
    # lifetime_value passed as float/str must not break comparison.
    assert "high_value" in evaluate(CustomerFacts(lifetime_value=500.0), CFG).segments
    assert "high_value" in evaluate(CustomerFacts(lifetime_value="750.00"), CFG).segments
