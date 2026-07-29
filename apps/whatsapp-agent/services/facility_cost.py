"""Backend facility-cost derivation (founder-approved model, 2026-07-29) — pure.

The facility cost is what a partner facility charges Laundry Khalas to fulfil an
order. It is the anchor for the negotiation floor / minimum selling price (spec
§3.2) and — with the central margin rule — for the customer quotation. The BACKEND
derives it; Claude never invents a facility cost or margin (CLAUDE.md §7).

Rules (founder):
  * Standard catalogue services → the selected facility's ACTIVE service-rate record,
    billed by the correct pricing unit × quantity / weight / item-count / square-metre.
  * Bespoke / restoration / luxury / inspection services → the selected valid facility
    QUOTATION for that item.
  * Apply the facility minimum charge and configured operational fees where applicable.
  * If NO valid rate or quotation exists for a line, the order cost is INCOMPLETE —
    return no number (the caller raises a durable facility-quotation request and marks
    the customer price pending; never an arbitrary price).

This module is pure/deterministic and offline: it operates on rate/quotation maps the
caller loads from the DB (db.repositories.facility_pricing_repo). Money is Decimal via
services.money.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from services import money

# Pricing types whose billable quantity is a MEASURE (weight / area), not a count.
_MEASURED_TYPES = frozenset({"PER_KG", "PER_SQM"})
# Pricing types that are inspection/quotation-based (no firm per-unit rate).
_QUOTE_TYPES = frozenset({"STARTING_FROM"})


def billable_quantity(pricing_type: str | None, quantity, measure) -> Decimal:
    """Units the facility rate is multiplied by: the supplied measure for measured
    (per-kg / per-sqm) lines, otherwise the item quantity/count."""
    if pricing_type in _MEASURED_TYPES:
        return money.to_decimal(measure) if measure is not None else money.round_money(0)
    return money.to_decimal(quantity if quantity is not None else 1)


def line_needs_quote(line: dict) -> bool:
    """A line is quotation-based (not standard-rate) when it is flagged bespoke /
    inspection or its pricing type is a 'from' starting price."""
    return bool(line.get("requires_quote")
                or line.get("requires_inspection")
                or line.get("is_starting_price")
                or line.get("pricing_type") in _QUOTE_TYPES)


@dataclass(frozen=True)
class FacilityCostResult:
    complete: bool                      # every line had a rate or a valid quotation
    facility_cost: Decimal | None       # None when incomplete — NEVER an arbitrary number
    subtotal: Decimal
    min_charge_applied: bool
    operational_fees: Decimal
    unpriced_lines: tuple[str, ...] = field(default=())

    def to_snapshot(self) -> dict:
        return {
            "kind": "facility_cost",
            "complete": self.complete,
            "facility_cost": float(self.facility_cost) if self.facility_cost is not None else None,
            "subtotal": float(self.subtotal),
            "min_charge_applied": self.min_charge_applied,
            "operational_fees": float(self.operational_fees),
            "unpriced_lines": list(self.unpriced_lines),
        }


def compute_facility_cost(lines: list[dict], rates: dict[str, float] | None, *,
                          quotations: dict[str, float] | None = None,
                          min_charge=0, operational_fees=0) -> FacilityCostResult:
    """Derive the facility cost for an order's lines.

    ``lines``: each ``{item_code, service_code, pricing_type, quantity, measure,
    requires_quote?, requires_inspection?, is_starting_price?}``.
    ``rates``: ``{service_code: rate}`` — the facility's active per-unit rate.
    ``quotations``: ``{item_code|service_code: amount}`` — facility-submitted quotes
    for bespoke/inspection lines.

    Any line with neither a rate nor a valid quotation makes the whole order cost
    INCOMPLETE (``facility_cost=None``) — the caller must then request a facility
    quotation and mark the price pending, never guess.
    """
    rates = rates or {}
    quotations = quotations or {}
    subtotal = money.round_money(0)
    unpriced: list[str] = []

    for ln in lines or []:
        code = ln.get("item_code") or ln.get("service_code") or "?"
        service_code = ln.get("service_code")
        if line_needs_quote(ln):
            q = quotations.get(ln.get("item_code")) or quotations.get(service_code)
            if q is None:
                unpriced.append(code)
            else:
                subtotal += money.to_decimal(q)
            continue
        rate = rates.get(service_code)
        if rate is None:
            unpriced.append(code)
            continue
        qty = billable_quantity(ln.get("pricing_type"), ln.get("quantity"), ln.get("measure"))
        subtotal += money.round_money(money.to_decimal(rate) * qty)

    subtotal = money.round_money(subtotal)
    if unpriced:
        # No arbitrary price: the order cannot be costed until a facility quotes it.
        return FacilityCostResult(False, None, subtotal, False,
                                  money.round_money(operational_fees), tuple(unpriced))

    min_c = money.round_money(min_charge)
    fees = money.round_money(operational_fees)
    min_applied = subtotal < min_c
    cost = money.round_money(max(subtotal, min_c) + fees)
    return FacilityCostResult(True, cost, subtotal, min_applied, fees, ())
