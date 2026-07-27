"""Facility rate → customer price (margin) + lowest-cost selection (pure).

The location-based better-rate workflow: among nearby qualified facilities that
OFFER the service, pick the lowest internal rate (distance as tie-break), apply the
active margin rule, and return ONLY the customer-facing price. Facility cost and
margin are NEVER surfaced (CLAUDE.md §7). All money is Decimal via services.money.
"""
from __future__ import annotations

import math
from decimal import Decimal

from services import money


def apply_margin(cost, rule: dict) -> Decimal:
    """Customer price = facility cost + margin. ``rule`` has margin_type
    ('percentage'|'fixed') + margin_value. Rounded HALF-UP to 2dp."""
    c = money.to_decimal(cost)
    mtype = (rule or {}).get("margin_type", "percentage")
    mval = money.to_decimal((rule or {}).get("margin_value", 0))
    if mtype == "fixed":
        return money.round_money(c + mval)
    return money.round_money(c * (Decimal(1) + mval / Decimal(100)))


def haversine_km(lat1, lon1, lat2, lon2) -> float | None:
    """Great-circle distance in km, or None if any coordinate is missing."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)), 2)


def pick_lowest(candidates: list[dict]) -> dict | None:
    """Lowest facility rate wins; distance (km) is the tie-break, then facility code
    for stability. Each candidate has ``rate`` (Decimal-able) and optional
    ``distance_km``. Never inspects margin (added after selection)."""
    if not candidates:
        return None

    def key(c):
        rate = money.to_decimal(c.get("rate", 0))
        dist = c.get("distance_km")
        dist = float(dist) if dist is not None else float("inf")
        return (rate, dist, str(c.get("facility_code") or ""))

    return sorted(candidates, key=key)[0]


def customer_quote(candidate: dict, margin_rule: dict) -> dict:
    """Build the customer-facing quote from a chosen candidate + margin rule.
    Returns ONLY customer-safe fields — no cost, no margin."""
    price = apply_margin(candidate.get("rate", 0), margin_rule)
    return {
        "facility_id": candidate.get("facility_id"),
        "facility_code": candidate.get("facility_code"),
        "customer_price_aed": float(price),
        "currency": candidate.get("currency", "AED"),
        "distance_km": candidate.get("distance_km"),
    }
