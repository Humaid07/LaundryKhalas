"""Centralized service-rule registry (spec §17) — pure, over the published catalogue.

One place resolves a catalogue item to the rule that governs it: the pricing MODE, the
photo / inspection / facility-quote policies, express + discount eligibility, and the
stamped rule-set version. The runtime source of truth stays the published catalogue
(services/catalogue); this layer just derives the §17 rule shape so the agent and pricing
paths never scatter these decisions. Every resolved rule carries the ruleset version so a
quote can be traced to the exact rules that produced it.
"""
from __future__ import annotations

from dataclasses import dataclass

from services import catalogue
from settings import get_settings

# --- pricing modes (spec §17) ------------------------------------------------
EXACT = "EXACT"
FROM = "FROM"
RANGE = "RANGE"
FACILITY_QUOTE = "FACILITY_QUOTE"
MEASURED = "MEASURED"
WEIGHT_CONFIRMED = "WEIGHT_CONFIRMED"
B2B_SALES_QUOTE = "B2B_SALES_QUOTE"

# Express is limited to these categories (spec §19).
_EXPRESS_CATEGORIES = frozenset({"WASH_FOLD", "CLEAN_PRESS", "PRESS_ONLY"})
# Categories where a photo is required up front (spec §18: bags, restoration; plus
# designer / leather / wedding items detected by keyword below).
_PHOTO_CATEGORIES = frozenset({"BAG_CARE", "RESTORATION"})
_SPECIALIST_CATEGORIES = frozenset({"RESTORATION", "BAG_CARE"})
_PHOTO_KEYWORDS = ("designer", "leather", "wedding", "suede")


@dataclass(frozen=True)
class ServiceRule:
    item_code: str
    market: str
    currency: str
    pricing_mode: str
    unit: str
    base_price: float | None
    minimum_charge: float | None
    photo_required: bool
    inspection_required: bool
    facility_quote_required: bool
    express_eligible: bool
    discount_eligible: bool
    specialist_required: bool
    measurement_required: bool
    active: bool
    rule_version: str


def pricing_mode(item: dict) -> str:
    """Derive the §17 pricing mode from the catalogue item."""
    ptype = item.get("pricing_type")
    if ptype == "INSPECTION_REQUIRED" or item.get("current_price") is None:
        return FACILITY_QUOTE
    if ptype == "PER_KG":
        return WEIGHT_CONFIRMED
    if ptype == "PER_SQM":
        return MEASURED
    if item.get("is_starting_price"):
        return FROM
    return EXACT


def resolve_rule(item_code: str, *, market: str = "AE") -> ServiceRule | None:
    """The governing rule for a catalogue item, or None if unknown."""
    item = catalogue.item_by_code(item_code)
    if not item:
        return None
    mode = pricing_mode(item)
    cat = item.get("category_code") or ""
    low = (item_code or "").lower()
    photo = cat in _PHOTO_CATEGORIES or any(k in low for k in _PHOTO_KEYWORDS)
    currency = (catalogue.market_currency(market)
                if market and market != "AE" else catalogue.currency())
    return ServiceRule(
        item_code=item_code,
        market=market,
        currency=currency,
        pricing_mode=mode,
        unit=item.get("pricing_unit", "ITEM"),
        base_price=item.get("current_price"),
        minimum_charge=item.get("minimum_charge"),
        photo_required=bool(photo),
        inspection_required=bool(item.get("requires_inspection")),
        facility_quote_required=(mode == FACILITY_QUOTE),
        express_eligible=cat in _EXPRESS_CATEGORIES,
        # A discount only applies to a firm/known total — never a From / facility-quote
        # / B2B price (spec §15 rule 6).
        discount_eligible=mode in (EXACT, MEASURED, WEIGHT_CONFIRMED),
        specialist_required=cat in _SPECIALIST_CATEGORIES or "designer" in low,
        # Both measured modes confirm quantity at pickup (sqm measured / kg weighed).
        measurement_required=bool(item.get("requires_measurement")) or mode in (MEASURED, WEIGHT_CONFIRMED),
        active=bool(item.get("active", True)),
        rule_version=get_settings().whatsapp_service_ruleset_version,
    )
