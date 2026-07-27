"""Deterministic CRM lifecycle + segment engine (backend-authoritative).

ONE place that decides a customer's CRM ``lifecycle_stage`` (single primary
relationship tier), ``funnel_stage`` (single position in the acquisition funnel)
and ``segments`` (a set of non-exclusive descriptive tags) from plain aggregate
FACTS. Thresholds come from ``config/crm_segments.json`` — never hardcoded.

This module is PURE and side-effect-free: it takes a facts dict + config and
returns a result dict. The LLM never assigns these values (CLAUDE.md: deterministic
backend logic stays authoritative; Claude must not arbitrarily assign customer
value, lifecycle stage or complaint risk). ``db/repositories/crm_repo.py`` gathers
the facts via SQL and persists the result.

Segment definitions (see config ``notes``):
  * repeat_customer   — confirmed_order_count >= repeat_min (two+ confirmed cycles)
  * new_customer      — 1 <= confirmed_order_count < repeat_min
  * high_value        — lifetime_value >= high_value_lifetime_value
  * price_sensitive   — many discount requests, or many price enquiries w/o booking
  * bespoke           — has ordered/enquired a bespoke / inspection service
  * campaign_responder— confirmed booking within the campaign window (later slice)
  * complaint_open    — has an open complaint
  * b2b_lead          — flagged as a B2B enquiry
  * inactive          — was active but has gone quiet beyond inactive_days
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services import money

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "crm_segments.json"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with _CONFIG_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_thresholds(config: dict | None = None) -> dict:
    return (config or _load_config())["thresholds"]


@dataclass(frozen=True)
class CustomerFacts:
    """Aggregates a customer's CRM state is derived from. All optional; a brand-new
    contact is all-zero. Money as Decimal-safe input."""
    confirmed_order_count: int = 0
    lifetime_value: Decimal = Decimal("0")
    discount_request_count: int = 0
    price_enquiry_count: int = 0
    has_bespoke: bool = False
    has_open_complaint: bool = False
    is_b2b: bool = False
    has_active_draft: bool = False
    campaign_responder: bool = False
    has_any_activity: bool = False
    days_since_activity: int | None = None  # None = never/unknown

    def __post_init__(self):
        # Coerce money to Decimal safely (never float arithmetic on currency).
        object.__setattr__(self, "lifetime_value", money.to_decimal(self.lifetime_value))


@dataclass(frozen=True)
class CrmResult:
    lifecycle_stage: str
    funnel_stage: str
    segments: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "lifecycle_stage": self.lifecycle_stage,
            "funnel_stage": self.funnel_stage,
            "segments": list(self.segments),
        }


def _is_inactive(facts: CustomerFacts, inactive_days: int) -> bool:
    return (
        facts.has_any_activity
        and facts.days_since_activity is not None
        and facts.days_since_activity >= inactive_days
    )


def compute_segments(facts: CustomerFacts, config: dict | None = None) -> list[str]:
    """Non-exclusive descriptive segment tags, deterministically ordered."""
    t = get_thresholds(config)
    repeat_min = int(t["repeat_min_confirmed_orders"])
    high_value = money.to_decimal(t["high_value_lifetime_value"])
    min_disc = int(t["price_sensitive_min_discount_requests"])
    min_enq = int(t["price_sensitive_min_price_enquiries"])
    inactive_days = int(t["inactive_days"])

    tags: list[str] = []
    if facts.confirmed_order_count >= repeat_min:
        tags.append("repeat_customer")
    elif facts.confirmed_order_count >= 1:
        tags.append("new_customer")

    if facts.lifetime_value >= high_value:
        tags.append("high_value")

    price_sensitive = facts.discount_request_count >= min_disc or (
        facts.confirmed_order_count == 0 and facts.price_enquiry_count >= min_enq
    )
    if price_sensitive:
        tags.append("price_sensitive")

    if facts.has_bespoke:
        tags.append("bespoke")
    if facts.campaign_responder:
        tags.append("campaign_responder")
    if facts.has_open_complaint:
        tags.append("complaint_open")
    if facts.is_b2b:
        tags.append("b2b_lead")
    if _is_inactive(facts, inactive_days):
        tags.append("inactive")

    # Deterministic order (stable across recomputes): keep the canonical sequence.
    canonical = [
        "repeat_customer", "new_customer", "high_value", "price_sensitive",
        "bespoke", "campaign_responder", "complaint_open", "b2b_lead", "inactive",
    ]
    return [s for s in canonical if s in tags]


def compute_lifecycle_stage(facts: CustomerFacts, config: dict | None = None) -> str:
    """Single primary relationship tier (precedence: B2B > complaint > repeat >
    active > inactive-lead > lead)."""
    t = get_thresholds(config)
    repeat_min = int(t["repeat_min_confirmed_orders"])
    inactive_days = int(t["inactive_days"])

    if facts.is_b2b:
        return "b2b_lead"
    if facts.has_open_complaint:
        return "complaint_open"
    if facts.confirmed_order_count >= repeat_min:
        return "repeat_customer"
    if facts.confirmed_order_count >= 1:
        return "active_customer"
    if _is_inactive(facts, inactive_days):
        return "inactive"
    return "lead"


def compute_funnel_stage(facts: CustomerFacts, config: dict | None = None) -> str:
    """Single position in the acquisition funnel (highest reached)."""
    if facts.confirmed_order_count >= 1:
        return "BOOKING_CONFIRMED"
    if facts.has_active_draft:
        return "BOOKING_STARTED"
    if facts.price_enquiry_count >= 1:
        return "PRICE_ENQUIRY"
    return "NEW_ENQUIRY"


def evaluate(facts: CustomerFacts, config: dict | None = None) -> CrmResult:
    """Compute the full CRM result for a customer in one deterministic pass."""
    return CrmResult(
        lifecycle_stage=compute_lifecycle_stage(facts, config),
        funnel_stage=compute_funnel_stage(facts, config),
        segments=compute_segments(facts, config),
    )
