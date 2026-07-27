"""Currency-safe money math and the ONE definition of a customer-facing price.

Every published Laundry Khalas price (website, approved price-list image,
catalogue, admin Pricing Management) is ALREADY a final, VAT-inclusive customer
price. The customer-facing price is therefore the stored price UNCHANGED — no
5% is ever added on top (task spec §§1-4). This module is the single shared
money utility so that rule is enforced in exactly one place and no component
re-implements price arithmetic.

Rules:
  * Decimal arithmetic only — never binary float — for money (spec §3/§6).
  * Round HALF-UP to 2 decimal places (the project's currency policy).
  * ``prices_include_vat`` defaults to True: the stored price is already final
    and is returned unchanged — AED 60 stays AED 60, AED 9 stays AED 9. The
    legacy ``prices_include_vat=False`` branch (add 5%) is retained ONLY for
    completeness; no live catalogue uses it, so the 5% is never added twice.
  * Per §6: the final UNIT price is rounded first, then the line total is
    (final unit × quantity), and the order total is the sum of final line
    totals — so the customer total is internally consistent with the per-line
    figures shown.

Customer-facing callers use ``final_*`` + ``format_money``; nothing here ever
emits the words "VAT"/"tax" — that wording is forbidden on customer channels
(spec §4). Internal accounting may still split the tax component OUT of an
inclusive total via ``vat_breakdown`` (never adding to the customer price).
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


def final_unit_price(base_price, *, vat_rate, prices_include_vat: bool = True) -> Decimal:
    """The final customer-facing unit price.

    Published prices are VAT-inclusive, so ``prices_include_vat=True`` (the
    default) returns the stored price (rounded) UNCHANGED — no 5% is added
    (spec §§1-4). The legacy ``prices_include_vat=False`` branch (add 5%) is
    retained only for completeness and is not used by any live catalogue.
    """
    base = to_decimal(base_price)
    if prices_include_vat:
        return round_money(base)
    return round_money(base * (Decimal(1) + to_decimal(vat_rate)))


def final_line_total(unit_price, quantity, *, vat_rate, prices_include_vat: bool = True) -> Decimal:
    """Final line total = round(final unit price) × quantity (§6)."""
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
