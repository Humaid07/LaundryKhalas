"""Facility revised-quote policy (pure, deterministic).

When a facility identifies work outside the approved standard price it proposes a
new FACILITY fee. Operations reviews it; the BACKEND then computes the
customer-facing price from the approved margin rule (reusing
services.facility_pricing.apply_margin) — never the LLM, and never exposing the
facility fee or margin to the customer. The customer must approve before the
affected work continues.

This module owns the state machine + the price computation; the asyncpg
persistence lives in db/repositories/facility_quote_revisions_repo.py.
"""

from __future__ import annotations

from services import facility_pricing, money

# status → the statuses it may transition to.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending_ops_review": frozenset({"ops_approved", "customer_pending", "ops_rejected"}),
    "ops_approved": frozenset({"customer_pending"}),
    "customer_pending": frozenset({"customer_approved", "customer_rejected"}),
    "customer_approved": frozenset(),
    "ops_rejected": frozenset(),
    "customer_rejected": frozenset(),
}

TERMINAL = frozenset({"customer_approved", "ops_rejected", "customer_rejected"})
# The customer's affected work stays paused until the revision reaches this state.
UNBLOCKS_WORK = "customer_approved"


def can_transition(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


def compute_customer_price(facility_fee, margin_rule: dict | None) -> float:
    """Customer-facing price for a revised facility fee, via the approved margin
    rule. Deterministic (Decimal, HALF-UP). Defaults to a 30% margin when no rule
    is supplied so a price is always grounded in a rule, never invented ad hoc."""
    rule = margin_rule or {"margin_type": "percentage", "margin_value": 30}
    return float(facility_pricing.apply_margin(money.to_decimal(facility_fee), rule))


def validate_fee(facility_fee) -> bool:
    """A revised fee must be a positive amount."""
    try:
        return money.to_decimal(facility_fee) > 0
    except Exception:  # noqa: BLE001 — any non-numeric is invalid
        return False
