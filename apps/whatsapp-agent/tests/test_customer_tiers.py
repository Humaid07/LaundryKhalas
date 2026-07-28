"""Backend-authoritative customer loyalty tier (New/Repeat/Bronze/Silver/Gold).
Pure + deterministic — config-driven, no LLM, no DB (services/crm_segments)."""
from decimal import Decimal

import pytest

from services import crm_segments as crm
from services.crm_segments import CustomerFacts, compute_customer_tier


def _facts(orders=0, value="0"):
    return CustomerFacts(confirmed_order_count=orders, lifetime_value=Decimal(value))


@pytest.mark.parametrize("orders, value, expected", [
    (0,  "0",     "NEW"),            # no completed order → NEW
    (1,  "50",    "REPEAT"),         # ≥1 but below Bronze → REPEAT
    (3,  "100",   "REPEAT"),         # still below Bronze (4 orders / 500 value)
    (4,  "0",     "REPEAT_BRONZE"),  # Bronze by order count
    (1,  "500",   "REPEAT_BRONZE"),  # Bronze by lifetime value (either/or)
    (10, "0",     "REPEAT_SILVER"),  # Silver by order count
    (2,  "1500",  "REPEAT_SILVER"),  # Silver by value
    (20, "0",     "REPEAT_GOLD"),    # Gold by order count
    (5,  "3000",  "REPEAT_GOLD"),    # Gold by value
])
def test_tier_thresholds(orders, value, expected):
    assert compute_customer_tier(_facts(orders, value)) == expected


def test_highest_tier_wins():
    # Meets multiple tiers → the highest (Gold) is returned.
    assert compute_customer_tier(_facts(25, "5000")) == "REPEAT_GOLD"


def test_tier_is_deterministic_idempotent():
    f = _facts(12, "1600")
    assert compute_customer_tier(f) == compute_customer_tier(f) == "REPEAT_SILVER"


def test_tier_configurable_not_hardcoded():
    # A different config (e.g. another market) changes the thresholds.
    cfg = {"customer_tiers": {"rule_version": "market-QA-1", "tiers": [
        {"tier": "REPEAT_GOLD", "min_completed_orders": 3, "min_lifetime_value": 0}]}}
    assert compute_customer_tier(_facts(3, "0"), cfg) == "REPEAT_GOLD"
    assert crm.customer_tier_rule_version(cfg) == "market-QA-1"


def test_evaluate_includes_tier_and_version():
    res = crm.evaluate(_facts(20, "3000"))
    assert res.customer_tier == "REPEAT_GOLD"
    assert res.customer_tier_rule_version == "1"
    d = res.as_dict()
    assert d["customer_tier"] == "REPEAT_GOLD" and d["customer_tier_rule_version"] == "1"


def test_new_customer_never_tiered_by_value_alone():
    # 0 completed orders is ALWAYS NEW even with a (leftover) value figure.
    assert compute_customer_tier(_facts(0, "9999")) == "NEW"
