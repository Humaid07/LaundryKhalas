"""Deterministic quote calculation over the item catalogue — final customer prices.

The single place the system turns catalogue items + quantities into money. It
NEVER invents a price and NEVER presents a starting ('From') or
inspection-dependent price as a guaranteed total (CLAUDE.md §5/§8, task spec
§§2/8/9).

CUSTOMER-FACING PRICES ARE FINAL. Catalogue prices are ALREADY VAT-inclusive
customer prices, so every price this module exposes for display (unit price,
line total, order total) is the stored price UNCHANGED — no 5% is added on top
(spec §§1-4), computed via ``services.money``. No customer-facing string ever
mentions VAT/tax (spec §4) — the tax split is kept only as internal accounting
fields (§3). Money is computed with Decimal, HALF-UP to 2dp (spec §3/§6).

Line kinds:
  * ``exact``    — fixed per-item / per-pair / per-bag price × quantity. Firm.
  * ``estimate`` — per-sqm with a supplied measurement, or per-kg additional
                   weight with a supplied weight. Firm math, but the final
                   quantity is confirmed at pickup, so the total is an estimate.
  * ``pending``  — 'From' / inspection-required items with no firm total. Shown
                   as "from AED X per unit"; excluded from the payable subtotal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services import catalogue, discount, money


@dataclass
class QuoteLine:
    item_code: str
    name: str
    quantity: float
    unit: str
    unit_price: float | None          # FINAL customer unit price (5% included)
    base_unit_price: float | None     # internal: pre-adjustment unit price
    pricing_type: str
    is_starting_price: bool
    requires_inspection: bool
    requires_measurement: bool
    regular_price: float | None
    line_total: float | None          # FINAL customer line total; None for pending
    base_line_total: float | None     # internal accounting: pre-adjustment total
    line_kind: str                    # 'exact' | 'estimate' | 'pending'
    measure: float | None = None      # sqm or kg supplied for measured lines

    def to_dict(self) -> dict:
        return {
            "item_code": self.item_code,
            "name": self.name,
            "quantity": self.quantity,
            "pricing_unit": self.unit,
            # unit_price / line_total are the CUSTOMER-FACING (final) figures so
            # every downstream consumer (dashboard, snapshot) shows final money
            # without re-doing the adjustment. base_* are internal accounting.
            "unit_price": self.unit_price,
            "base_unit_price": self.base_unit_price,
            "pricing_type": self.pricing_type,
            "is_starting_price": self.is_starting_price,
            "requires_inspection": self.requires_inspection,
            "requires_measurement": self.requires_measurement,
            "regular_price": self.regular_price,
            "line_total": self.line_total,
            "base_line_total": self.base_line_total,
            "line_kind": self.line_kind,
            "measure": self.measure,
        }


@dataclass
class Quote:
    currency: str
    vat_rate: float
    prices_include_vat: bool
    lines: list[QuoteLine] = field(default_factory=list)
    # Internal accounting only (spec §3) — NEVER shown to a customer. Derived
    # from the FINAL (post-discount) customer total.
    subtotal_excluding_vat: float = 0.0
    vat_amount: float = 0.0
    # The final customer total the customer PAYS: eligible subtotal minus any
    # automatic order discount. Kept under this name for the existing order-row
    # column mapping.
    estimated_total_including_vat: float = 0.0
    # Automatic order-level discount (spec §§5-11). eligible_subtotal is the
    # pre-discount sum of final line totals; discount_amount is 0 when the order
    # does not qualify (subtotal <= threshold) or the exact total is unknown.
    eligible_subtotal: float = 0.0
    discount_applied: bool = False
    discount_reason: str = "below_threshold"
    discount_requested: bool = False
    discount_rule_code: str | None = None
    discount_rule_version: str | None = None
    discount_percentage: float | None = None
    discount_threshold: float | None = None
    discount_amount: float = 0.0
    has_starting_prices: bool = False
    has_pending_inspection: bool = False
    has_measured_estimate: bool = False
    is_final: bool = True          # False when any pending/estimate line exists
    disclaimer: str = ""

    @property
    def is_estimated(self) -> bool:
        return not self.is_final

    @property
    def customer_total(self) -> float:
        """Alias with a VAT-free name — the final amount the customer sees/pays."""
        return self.estimated_total_including_vat

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "vat_rate": self.vat_rate,
            "prices_include_vat": self.prices_include_vat,
            "lines": [ln.to_dict() for ln in self.lines],
            "subtotal_excluding_vat": self.subtotal_excluding_vat,
            "vat_amount": self.vat_amount,
            "estimated_total_including_vat": self.estimated_total_including_vat,
            "customer_total": self.estimated_total_including_vat,
            "eligible_subtotal": self.eligible_subtotal,
            "discount_applied": self.discount_applied,
            "discount_reason": self.discount_reason,
            "discount_requested": self.discount_requested,
            "discount_rule_code": self.discount_rule_code,
            "discount_rule_version": self.discount_rule_version,
            "discount_percentage": self.discount_percentage,
            "discount_threshold": self.discount_threshold,
            "discount_amount": self.discount_amount,
            "has_starting_prices": self.has_starting_prices,
            "has_pending_inspection": self.has_pending_inspection,
            "has_measured_estimate": self.has_measured_estimate,
            "is_final": self.is_final,
            "is_estimated": self.is_estimated,
            "disclaimer": self.disclaimer,
        }


def _line_for(item: dict, quantity: float, measure: float | None,
              vat_rate: float, prices_include_vat: bool,
              override_price: float | None = None,
              force_pending: bool = False) -> QuoteLine:
    ptype = item["pricing_type"]
    # A published/promotional price (from the price resolver) OR a per-market price
    # overrides the static catalogue price so the agent quotes the CURRENT value with
    # no restart. Falls back to the catalogue price when no override is supplied.
    # ``force_pending`` means this item has NO configured price in the active market
    # (spec §8) — it is priced after inspection, never quoted with another market's
    # number.
    base_price = None if force_pending else (
        override_price if override_price is not None else item.get("current_price"))
    unit = item["pricing_unit"]
    starting = item["is_starting_price"]
    inspection = item["requires_inspection"] or force_pending
    measured = item["requires_measurement"] or ptype in ("PER_SQM", "PER_KG")

    def _final_unit(p):
        return None if p is None else float(
            money.final_unit_price(p, vat_rate=vat_rate, prices_include_vat=prices_include_vat))

    final_unit = _final_unit(base_price)

    # Pending: a 'from'/inspection price never becomes a firm total.
    if starting or inspection or base_price is None:
        kind, base_total, final_total = "pending", None, None
    elif measured:
        # Firm per-unit math, but the measured quantity is confirmed at pickup.
        if measure is not None:
            kind = "estimate"
            base_total = float(money.round_money(money.to_decimal(base_price) * money.to_decimal(measure)))
            final_total = float(money.final_line_total(
                base_price, measure, vat_rate=vat_rate, prices_include_vat=prices_include_vat))
        else:
            kind, base_total, final_total = "pending", None, None
    else:
        kind = "exact"
        base_total = float(money.round_money(money.to_decimal(base_price) * money.to_decimal(quantity)))
        final_total = float(money.final_line_total(
            base_price, quantity, vat_rate=vat_rate, prices_include_vat=prices_include_vat))

    return QuoteLine(
        item_code=item["item_code"],
        name=item["canonical_name"],
        quantity=quantity,
        unit=unit,
        unit_price=final_unit,
        base_unit_price=None if base_price is None else float(base_price),
        pricing_type=ptype,
        is_starting_price=starting,
        requires_inspection=inspection,
        requires_measurement=measured,
        regular_price=item.get("regular_price"),
        line_total=final_total,
        base_line_total=base_total,
        line_kind=kind,
        measure=measure,
    )


def _no_discount(subtotal, reason: str) -> "discount.DiscountResult":
    zero = money.round_money(0)
    return discount.DiscountResult(
        applied=False, reason=reason, rule_code=None, eligible_subtotal=subtotal,
        threshold=None, discount_percentage=None, discount_amount=zero,
        final_total=subtotal, discount_requested=False, rule_version=None)


def _negotiated_discount(subtotal, final_total) -> "discount.DiscountResult":
    """A negotiated final total (from services/negotiation via the negotiate tool)
    applied exactly as the customer's price. The percentage is derived only for
    display/logging; the money that governs is the negotiated final total."""
    final = money.round_money(final_total)
    amount = money.round_money(subtotal - final)
    pct = (money.round_money(amount / subtotal * money.to_decimal(100))
           if subtotal > 0 else money.round_money(0))
    return discount.DiscountResult(
        applied=amount > money.round_money(0), reason="negotiated", rule_code="NEGOTIATED",
        eligible_subtotal=subtotal, threshold=None, discount_percentage=pct,
        discount_amount=amount, final_total=final, discount_requested=True,
        rule_version="negotiation")


def _resolve_discount(subtotal, *, total_is_known: bool, discount_requested: bool,
                      negotiated_final_total: float | None) -> "discount.DiscountResult":
    """The SINGLE decision on what discount (if any) applies to a known subtotal.

    Order of precedence:
      1. A negotiated final total (the negotiation tool already decided it) — used
         exactly, as long as it is a sane 0 < final <= subtotal.
      2. Otherwise, the legacy AUTOMATIC order discount — ONLY when the operator has
         re-enabled it (auto_order_discount_enabled). Retired by default (founder
         decision: negotiation-only).
      3. Otherwise, no discount — the full baseline price is quoted (spec §2.1).
    """
    if not total_is_known or subtotal <= money.round_money(0):
        return _no_discount(subtotal, "unknown_total" if not total_is_known else "below_threshold")
    if negotiated_final_total is not None:
        final = money.round_money(negotiated_final_total)
        if money.round_money(0) < final <= subtotal:
            return _negotiated_discount(subtotal, final)
        return _no_discount(subtotal, "negotiation_invalid")
    from settings import get_settings
    if get_settings().auto_order_discount_enabled:
        return discount.evaluate(subtotal, total_is_known=True, discount_requested=discount_requested)
    return _no_discount(subtotal, "negotiation_only")


def calculate_estimate(order_items: list[dict],
                       price_overrides: dict[str, float] | None = None,
                       *, discount_requested: bool = False,
                       negotiated_final_total: float | None = None,
                       market: str = "AE") -> Quote:
    """Compute a quote for ``order_items`` with FINAL customer prices.

    Each entry: ``{"item_code": str, "quantity": number, "measure": number?}``
    (``measure`` = sqm for per-sqm items or kg for additional-weight lines).
    Unknown/inactive item codes are skipped. Returns a :class:`Quote` whose
    order total is the sum of FINAL line totals (5% already included, spec §20);
    pending 'From'/inspection lines are itemised but excluded from the payable
    total, and set ``is_final=False`` so the caller labels the total estimated.

    ``price_overrides`` (``{item_code: price}``) supplies CURRENT published /
    promotional unit prices from ``services.price_resolver``; omitted → the
    static catalogue price is used.
    """
    vat = catalogue.vat_rate()
    incl = catalogue.prices_include_vat()
    # Per-market pricing (spec §8): a non-AE market with its own price list supplies
    # the money in its own currency; items it does NOT price become inspection lines
    # (never quoted with the AE number). AE uses the base catalogue unchanged.
    is_market_priced = market not in (None, "AE") and catalogue.has_market_pricing(market)
    market_map = catalogue.market_prices(market) if is_market_priced else {}
    quote = Quote(
        currency=catalogue.market_currency(market) if is_market_priced else catalogue.currency(),
        vat_rate=vat,
        prices_include_vat=incl,
        disclaimer=catalogue.pricing_disclaimer(),
    )
    # Sum FINAL line totals (per-unit rounded), so the order total matches the
    # per-line figures the customer sees exactly (spec §20).
    customer_total = money.to_decimal(0)
    for entry in order_items or []:
        item = catalogue.item_by_code(entry.get("item_code"))
        if not item or not item.get("active", True):
            continue
        qty = _coerce_number(entry.get("quantity"), default=1.0)
        measure = _coerce_number(entry.get("measure"), default=None)
        code = item["item_code"]
        if is_market_priced:
            # The market's price is authoritative; an item the market does not price
            # is inspection-only (never falls back to the AE catalogue number).
            override = market_map.get(code)
            force_pending = code not in market_map
        else:
            override = (price_overrides or {}).get(code)
            force_pending = False
        line = _line_for(item, qty, measure, vat, incl,
                         override_price=override, force_pending=force_pending)
        quote.lines.append(line)
        if line.line_kind in ("exact", "estimate") and line.line_total is not None:
            customer_total += money.to_decimal(line.line_total)
        if line.is_starting_price:
            quote.has_starting_prices = True
        if line.line_kind == "pending":
            quote.has_pending_inspection = quote.has_pending_inspection or line.requires_inspection
        if line.line_kind == "estimate":
            quote.has_measured_estimate = True

    eligible_subtotal = money.round_money(customer_total)
    has_pending = quote.has_pending_inspection or any(
        ln.line_kind == "pending" for ln in quote.lines)
    # LABEL: an order is "final" only when every line is a firm exact total. A
    # measured estimate (per-sqm/per-kg with a supplied measurement) is still an
    # ESTIMATE for labelling — the final quantity is confirmed at pickup.
    quote.is_final = not (has_pending or quote.has_measured_estimate)
    # DISCOUNT (founder decision 2026-07-29: NEGOTIATION-ONLY). By default no
    # automatic discount is applied — the FULL baseline price is quoted (spec §2.1).
    # A discount appears only when the negotiation tool passes an agreed
    # ``negotiated_final_total`` (the §3 ladder / facility-floor), or when the legacy
    # automatic engine is explicitly re-enabled (auto_order_discount_enabled). The
    # exact total is KNOWN when there is no 'from'/inspection ('pending') line and
    # the subtotal is positive (a measured estimate counts as known); an unknown
    # 'from'/inspection total is never discounted (spec §8).
    total_is_known = (not has_pending) and eligible_subtotal > money.round_money(0)
    disc = _resolve_discount(eligible_subtotal, total_is_known=total_is_known,
                             discount_requested=discount_requested,
                             negotiated_final_total=negotiated_final_total)
    quote.discount_requested = discount_requested or disc.discount_requested
    quote.eligible_subtotal = float(eligible_subtotal)
    quote.discount_applied = disc.applied
    quote.discount_reason = disc.reason
    quote.discount_rule_code = disc.rule_code
    quote.discount_percentage = float(disc.discount_percentage) if disc.discount_percentage is not None else None
    quote.discount_threshold = float(disc.threshold) if disc.threshold is not None else None
    quote.discount_amount = float(disc.discount_amount)
    quote.discount_rule_version = disc.rule_version

    total = money.round_money(disc.final_total)   # customer pays post-discount
    # Internal accounting split (never shown): net + tax == final total exactly.
    net, tax = money.vat_breakdown(total, vat_rate=vat)
    quote.subtotal_excluding_vat = float(net)
    quote.vat_amount = float(tax)
    quote.estimated_total_including_vat = float(total)
    return quote


def _coerce_number(v, default):
    if v is None:
        return default
    try:
        n = float(v)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


# --- Customer-facing quote wording (FINAL prices, no VAT wording — spec §§11/23) ---
def format_quote_lines(quote: Quote) -> list[str]:
    """Human lines for the WhatsApp summary / dashboard, one per order line.
    Shows only FINAL customer amounts; never any VAT/tax wording (spec §§11/23)."""
    cur = quote.currency or "AED"
    out: list[str] = []
    for ln in quote.lines:
        qty = _fmt_qty(ln.quantity)
        if ln.line_kind == "exact":
            out.append(f"{qty} × {ln.name} — {cur} {money.format_money(ln.line_total)}")
        elif ln.line_kind == "estimate":
            out.append(
                f"{ln.name}: {_fmt_qty(ln.measure)} {ln.unit.lower()} "
                f"— {cur} {money.format_money(ln.line_total)} (confirmed after measuring)"
            )
        else:  # pending (a 'from'/starting or inspection line)
            unit = ln.unit.lower()
            if ln.unit_price is not None:
                # Only a genuine inspection line carries the "after inspection" tail;
                # a routine starting price (e.g. standard alterations, spec §5) reads
                # cleanly as "from AED X per item".
                tail = " (final price after inspection)" if ln.requires_inspection else ""
                out.append(
                    f"{qty} × {ln.name}: from {cur} {money.format_money(ln.unit_price)} per {unit}{tail}"
                )
            else:
                out.append(f"{qty} × {ln.name}: price confirmed after inspection")
    return out


def format_quote_summary(quote: Quote) -> str:
    """Full multi-line quote block for the booking confirmation summary. Shows a
    single FINAL amount — no subtotal, no VAT line, no tax wording (spec §23)."""
    cur = quote.currency or "AED"
    lines = format_quote_lines(quote)
    body = "\n".join(lines)
    label = "Estimated price" if quote.is_estimated else "Final price"
    if quote.discount_applied and quote.discount_amount > 0:
        # Show the applied discount clearly: pre-discount estimate, the discount
        # off, then the revised amount the customer actually pays (spec §10). The
        # pre-discount figure is labelled "Original …", never the payable amount.
        # No VAT line anywhere (spec §4).
        revised_label = "Revised estimated price" if quote.is_estimated else "Revised price"
        pct = _fmt_qty(quote.discount_percentage)
        body += f"\nOriginal {'estimate' if quote.is_estimated else 'price'}: {cur} {money.format_money(quote.eligible_subtotal)}"
        body += f"\nSpecial {pct}% discount: -{cur} {money.format_money(quote.discount_amount)}"
        body += f"\n{revised_label}: {cur} {money.format_money(quote.estimated_total_including_vat)}"
    elif quote.estimated_total_including_vat > 0:
        body += f"\n{label} — {cur} {money.format_money(quote.estimated_total_including_vat)}"
    if quote.has_pending_inspection or any(ln.line_kind == "pending" for ln in quote.lines):
        body += "\n\nSome items are priced after inspection — the team will confirm the final price."
    if quote.has_measured_estimate:
        body += "\n\nMeasured items are estimated; the final measurement is confirmed at pickup."
    if quote.disclaimer:
        body += f"\n\n{quote.disclaimer}"
    return body


def _fmt_qty(v) -> str:
    if v is None:
        return "?"
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:g}"
