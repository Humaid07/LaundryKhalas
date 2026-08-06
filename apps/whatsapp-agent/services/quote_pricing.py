"""Customer-price calculation from a facility quote (pure, backend-authoritative).

Given a facility fee + the approved margin rule, compute the customer-facing price
and an IMMUTABLE snapshot. Reuses services.facility_pricing.apply_margin — Claude
never calculates or chooses the markup. The facility fee + markup never reach the
customer; only ``final_customer_price`` does.
"""

from __future__ import annotations

from services import facility_pricing, money

# Operations-review policy defaults (spec §12). Overridable via config.
_DEFAULT_REVIEW = {
    "amount_threshold": 300.0,      # any quote at/above this needs ops review
    "review_luxury": True,
    "review_restoration": True,
    "review_wedding": True,
    "min_margin_pct": 15.0,         # below this margin → review
}


def calculate_customer_price_from_facility_quote(
    facility_fee,
    *,
    margin_rule: dict | None,
    discount_percentage=0,
    delivery_charge=0,
    express_surcharge=0,
    currency: str = "AED",
    markup_rule_id: str | None = None,
    pricing_rule_version: str | None = None,
) -> dict:
    """Immutable customer-price snapshot. All money Decimal (HALF-UP) → float."""
    fee = money.to_decimal(facility_fee)
    rule = margin_rule or {"margin_type": "percentage", "margin_value": 30}
    subtotal = facility_pricing.apply_margin(fee, rule)
    disc_pct = money.to_decimal(discount_percentage or 0)
    discount_amount = money.round_money(subtotal * disc_pct / money.to_decimal(100)) if disc_pct else money.to_decimal(0)
    delivery = money.to_decimal(delivery_charge or 0)
    express = money.to_decimal(express_surcharge or 0)
    final = money.round_money(subtotal - discount_amount + delivery + express)
    return {
        "facility_fee": float(fee),
        "markup_type": rule.get("margin_type", "percentage"),
        "markup_value": float(money.to_decimal(rule.get("margin_value", 0))),
        "markup_rule_id": markup_rule_id,
        "customer_subtotal": float(subtotal),
        "discount_percentage": float(disc_pct),
        "discount_amount": float(discount_amount),
        "delivery_charge": float(delivery),
        "express_surcharge": float(express),
        "final_customer_price": float(final),
        "currency": currency,
        "pricing_rule_version": pricing_rule_version,
    }


def _margin_pct(snapshot: dict) -> float:
    fee = snapshot.get("facility_fee") or 0
    final = snapshot.get("final_customer_price") or 0
    if final <= 0:
        return 0.0
    return round((final - fee) / final * 100.0, 2)


def requires_operations_review(
    snapshot: dict,
    *,
    luxury: bool = False,
    restoration: bool = False,
    wedding: bool = False,
    scope_revised: bool = False,
    severe_damage: bool = False,
    open_complaint: bool = False,
    config: dict | None = None,
) -> tuple[bool, list[str]]:
    """Whether a facility quote must go through Operations before the customer.
    Returns (required, reasons)."""
    cfg = {**_DEFAULT_REVIEW, **(config or {})}
    reasons: list[str] = []
    final = snapshot.get("final_customer_price") or 0
    if final >= float(cfg["amount_threshold"]):
        reasons.append("ABOVE_AMOUNT_THRESHOLD")
    if luxury and cfg.get("review_luxury"):
        reasons.append("LUXURY_ITEM")
    if restoration and cfg.get("review_restoration"):
        reasons.append("RESTORATION")
    if wedding and cfg.get("review_wedding"):
        reasons.append("WEDDING_DRESS")
    if _margin_pct(snapshot) < float(cfg["min_margin_pct"]):
        reasons.append("BELOW_MIN_MARGIN")
    if scope_revised:
        reasons.append("REVISED_SCOPE")
    if severe_damage:
        reasons.append("SEVERE_EXISTING_DAMAGE")
    if open_complaint:
        reasons.append("OPEN_COMPLAINT")
    return (len(reasons) > 0, reasons)
