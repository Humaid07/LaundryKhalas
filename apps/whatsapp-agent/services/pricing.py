"""Deterministic VAT-aware quote calculation over the item catalogue.

The single place the system turns catalogue items + quantities into money. It
NEVER invents a price and NEVER presents a starting ('From') or
inspection-dependent price as a guaranteed total (CLAUDE.md §5/§8, task spec
§§2/8/9). Prices in the catalogue EXCLUDE 5% VAT; this module adds VAT only to
the exact portion of the order and clearly labels anything estimated or pending.

Line kinds:
  * ``exact``    — fixed per-item / per-pair / per-bag price × quantity. Firm.
  * ``estimate`` — per-sqm with a supplied measurement, or per-kg additional
                   weight with a supplied weight. Firm math, but the final
                   quantity is confirmed at pickup, so the total is an estimate.
  * ``pending``  — 'From' / inspection-required items with no firm total. Shown
                   as "from AED X per unit"; excluded from the payable subtotal.

Only the ``exact`` (+ firm ``estimate``) portion carries VAT and forms the
subtotal. If any pending line exists, ``is_final`` is False and the caller must
label the order total "estimated / final price pending inspection".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services import catalogue


@dataclass
class QuoteLine:
    item_code: str
    name: str
    quantity: float
    unit: str
    unit_price: float | None
    pricing_type: str
    is_starting_price: bool
    requires_inspection: bool
    requires_measurement: bool
    regular_price: float | None
    line_total: float | None      # None for pending (no firm total)
    line_kind: str                # 'exact' | 'estimate' | 'pending'
    measure: float | None = None  # sqm or kg supplied for measured lines

    def to_dict(self) -> dict:
        return {
            "item_code": self.item_code,
            "name": self.name,
            "quantity": self.quantity,
            "pricing_unit": self.unit,
            "unit_price": self.unit_price,
            "pricing_type": self.pricing_type,
            "is_starting_price": self.is_starting_price,
            "requires_inspection": self.requires_inspection,
            "requires_measurement": self.requires_measurement,
            "regular_price": self.regular_price,
            "line_total": self.line_total,
            "line_kind": self.line_kind,
            "measure": self.measure,
        }


@dataclass
class Quote:
    currency: str
    vat_rate: float
    prices_include_vat: bool
    lines: list[QuoteLine] = field(default_factory=list)
    subtotal_excluding_vat: float = 0.0
    vat_amount: float = 0.0
    estimated_total_including_vat: float = 0.0
    has_starting_prices: bool = False
    has_pending_inspection: bool = False
    has_measured_estimate: bool = False
    is_final: bool = True          # False when any pending/estimate line exists
    disclaimer: str = ""

    @property
    def is_estimated(self) -> bool:
        return not self.is_final

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "vat_rate": self.vat_rate,
            "prices_include_vat": self.prices_include_vat,
            "lines": [ln.to_dict() for ln in self.lines],
            "subtotal_excluding_vat": self.subtotal_excluding_vat,
            "vat_amount": self.vat_amount,
            "estimated_total_including_vat": self.estimated_total_including_vat,
            "has_starting_prices": self.has_starting_prices,
            "has_pending_inspection": self.has_pending_inspection,
            "has_measured_estimate": self.has_measured_estimate,
            "is_final": self.is_final,
            "is_estimated": self.is_estimated,
            "disclaimer": self.disclaimer,
        }


def _round(v: float) -> float:
    return round(float(v) + 1e-9, 2)


def _line_for(item: dict, quantity: float, measure: float | None,
              override_price: float | None = None) -> QuoteLine:
    ptype = item["pricing_type"]
    # A published/promotional price (from the price resolver) overrides the static
    # catalogue price so the agent quotes the CURRENT published value with no
    # restart. Falls back to the catalogue price when no override is supplied.
    price = override_price if override_price is not None else item.get("current_price")
    unit = item["pricing_unit"]
    starting = item["is_starting_price"]
    inspection = item["requires_inspection"]
    measured = item["requires_measurement"] or ptype in ("PER_SQM", "PER_KG")

    # Pending: a 'from'/inspection price never becomes a firm total.
    if starting or inspection or price is None:
        kind, total = "pending", None
    elif measured:
        # Firm per-unit math, but the measured quantity is confirmed at pickup.
        if measure is not None:
            kind, total = "estimate", _round(price * measure)
        else:
            kind, total = "pending", None
    else:
        kind, total = "exact", _round(price * quantity)

    return QuoteLine(
        item_code=item["item_code"],
        name=item["canonical_name"],
        quantity=quantity,
        unit=unit,
        unit_price=price,
        pricing_type=ptype,
        is_starting_price=starting,
        requires_inspection=inspection,
        requires_measurement=measured,
        regular_price=item.get("regular_price"),
        line_total=total,
        line_kind=kind,
        measure=measure,
    )


def calculate_estimate(order_items: list[dict],
                       price_overrides: dict[str, float] | None = None) -> Quote:
    """Compute a VAT-aware quote for ``order_items``.

    Each entry: ``{"item_code": str, "quantity": number, "measure": number?}``
    (``measure`` = sqm for per-sqm items or kg for additional-weight lines).
    Unknown/inactive item codes are skipped. Returns a :class:`Quote` whose
    subtotal/VAT/total cover ONLY the firm portion; pending 'From'/inspection
    lines are itemised but excluded from the payable total, and set
    ``is_final=False`` so the caller labels the total as estimated.

    ``price_overrides`` (``{item_code: price}``) supplies CURRENT published /
    promotional unit prices from ``services.price_resolver`` so the agent quotes
    the live published catalogue without a restart; omitted → the static
    catalogue price is used (identical behaviour to before).
    """
    vat = catalogue.vat_rate()
    quote = Quote(
        currency=catalogue.currency(),
        vat_rate=vat,
        prices_include_vat=catalogue.prices_include_vat(),
        disclaimer=catalogue.pricing_disclaimer(),
    )
    firm_subtotal = 0.0
    for entry in order_items or []:
        item = catalogue.item_by_code(entry.get("item_code"))
        if not item or not item.get("active", True):
            continue
        qty = _coerce_number(entry.get("quantity"), default=1.0)
        measure = _coerce_number(entry.get("measure"), default=None)
        override = (price_overrides or {}).get(item["item_code"])
        line = _line_for(item, qty, measure, override_price=override)
        quote.lines.append(line)
        if line.line_kind in ("exact", "estimate") and line.line_total is not None:
            firm_subtotal += line.line_total
        if line.is_starting_price:
            quote.has_starting_prices = True
        if line.line_kind == "pending":
            quote.has_pending_inspection = quote.has_pending_inspection or line.requires_inspection
        if line.line_kind == "estimate":
            quote.has_measured_estimate = True

    quote.subtotal_excluding_vat = _round(firm_subtotal)
    quote.vat_amount = _round(firm_subtotal * vat)
    quote.estimated_total_including_vat = _round(firm_subtotal + quote.vat_amount)
    # Not final if anything can't be firmly totalled yet.
    quote.is_final = not (
        quote.has_pending_inspection
        or quote.has_measured_estimate
        or any(ln.line_kind == "pending" for ln in quote.lines)
    )
    return quote


def _coerce_number(v, default):
    if v is None:
        return default
    try:
        n = float(v)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


# --- Customer-facing quote wording ------------------------------------------
def format_quote_lines(quote: Quote) -> list[str]:
    """Human lines for the WhatsApp summary / dashboard, one per order line."""
    out: list[str] = []
    for ln in quote.lines:
        qty = _fmt_qty(ln.quantity)
        if ln.line_kind == "exact":
            out.append(
                f"{qty} × {ln.name} × AED {_m(ln.unit_price)} = AED {_m(ln.line_total)}"
            )
        elif ln.line_kind == "estimate":
            out.append(
                f"{ln.name}: {_fmt_qty(ln.measure)} {ln.unit.lower()} × "
                f"AED {_m(ln.unit_price)} ≈ AED {_m(ln.line_total)} (confirmed after measuring)"
            )
        else:  # pending
            unit = ln.unit.lower()
            if ln.unit_price is not None:
                out.append(
                    f"{qty} × {ln.name}: from AED {_m(ln.unit_price)} per {unit} "
                    "(final price after inspection)"
                )
            else:
                out.append(f"{qty} × {ln.name}: price confirmed after inspection")
    return out


def format_quote_summary(quote: Quote) -> str:
    """Full multi-line quote block for the booking confirmation summary."""
    lines = format_quote_lines(quote)
    body = "\n".join(lines)
    if quote.subtotal_excluding_vat > 0:
        body += (
            f"\n\nSubtotal (excl. VAT): AED {_m(quote.subtotal_excluding_vat)}"
            f"\nVAT (5%): AED {_m(quote.vat_amount)}"
        )
        label = "Estimated total" if quote.is_estimated else "Total"
        body += f"\n{label} (incl. VAT): AED {_m(quote.estimated_total_including_vat)}"
    if quote.has_pending_inspection or any(ln.line_kind == "pending" for ln in quote.lines):
        body += "\n\nSome items are priced after inspection — the team will confirm the final price."
    if quote.has_measured_estimate:
        body += "\n\nMeasured items are estimated; the final measurement is confirmed at pickup."
    body += f"\n\n{quote.disclaimer}"
    return body


def _fmt_qty(v) -> str:
    if v is None:
        return "?"
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:g}"


def _m(v) -> str:
    if v is None:
        return "—"
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.2f}"
