"""Currency-safe money math and the ONE definition of a customer-facing price.

Every amount a customer ever sees is a "final customer price": the stored
catalogue/base price with the 5% adjustment ALREADY included (task spec
§§17-20). This module is the single shared utility for that calculation and for
money rounding, so the 5% is applied in exactly one place and never twice
(spec §18) and no component re-implements the arithmetic.

Rules:
  * Decimal arithmetic only — never binary float — for money (spec §19).
  * Round HALF-UP to 2 decimal places (the project's currency policy).
  * If the stored price already includes the adjustment
    (``prices_include_vat=True``) the final price is the stored price unchanged
    — the 5% is NOT applied again.
  * Per §20: the final UNIT price is rounded first, then the line total is
    (final unit × quantity), and the order total is the sum of final line
    totals — so the customer total is internally consistent with the per-line
    figures shown.

Customer-facing callers use ``final_*`` + ``format_money``; nothing here ever
emits the words "VAT"/"tax" — that wording is forbidden on customer channels
(spec §11). Internal accounting may still split base/vat via ``vat_breakdown``.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def to_decimal(value) -> Decimal:
    """Coerce any numeric/str to Decimal via str() so float noise never enters."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value) -> Decimal:
    """Round to 2dp, HALF-UP (currency policy)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def final_unit_price(base_price, *, vat_rate, prices_include_vat: bool = False) -> Decimal:
    """The customer-facing unit price with the 5% adjustment already applied.

    ``prices_include_vat=True`` → the stored price is already final, returned
    (rounded) unchanged — the adjustment is never applied a second time (§18).
    """
    base = to_decimal(base_price)
    if prices_include_vat:
        return round_money(base)
    return round_money(base * (Decimal(1) + to_decimal(vat_rate)))


def final_line_total(unit_price, quantity, *, vat_rate, prices_include_vat: bool = False) -> Decimal:
    """Final line total = round(final unit price) × quantity (§20)."""
    unit = final_unit_price(unit_price, vat_rate=vat_rate, prices_include_vat=prices_include_vat)
    return round_money(unit * to_decimal(quantity))


def vat_breakdown(final_total, *, vat_rate) -> tuple[Decimal, Decimal]:
    """INTERNAL accounting only (spec §24): split a final customer total back
    into (net, tax) so subtotal+tax == the final total exactly. Never shown to a
    customer. ``net = final / (1 + rate)``; ``tax = final - net``."""
    total = round_money(final_total)
    rate = to_decimal(vat_rate)
    net = round_money(total / (Decimal(1) + rate))
    return net, round_money(total - net)


def format_money(value) -> str:
    """Customer-facing amount: whole numbers show clean ('63'), otherwise 2dp
    ('7.35', '52.50'). No currency symbol, no VAT wording — the caller adds
    'AED '."""
    if value is None:
        return "—"
    v = round_money(value)
    if v == v.to_integral_value():
        return str(int(v))
    return f"{v:.2f}"
