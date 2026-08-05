"""Wash & Fold weight-optimisation engine (ruleset 2026_08_05).

Deterministic, backend-authoritative. Given a total weight the customer explicitly
asks to be estimated on, this returns the CHEAPEST valid customer price built from
the published Wash & Fold packages plus additional-kg — the model never does this
arithmetic itself (spec §18).

Published bands (read from the catalogue so there is ONE source of truth — no second
pricing module):
  * up to 6 kg           → a 6 kg package price (a bag below 6 kg still pays this)
  * 6.1 kg to 12 kg      → a 12 kg package price
  * above a 12 kg bag    → additional weight per kg (bag max 20 kg physical)

The old "AED 7 per additional kg" rule is gone — additional weight is now the
catalogue's WASH_FOLD_ADDITIONAL_KG price (AED/QAR 12 per kg).

Spec-anchored results (AED): 13 kg → 102, 18 kg → 150, 20 kg → 180, 24 kg → 180.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from services import catalogue
from settings import get_settings

# Physical limit for a single bag (a 12 kg package may carry up to 8 additional kg).
_BAG_MAX_KG = 20
_PKG_LIMIT_KG = 12

_6KG = "WASH_FOLD_6KG"
_12KG = "WASH_FOLD_12KG"
_ADDITIONAL_KG = "WASH_FOLD_ADDITIONAL_KG"


@dataclass
class WashFoldQuote:
    total_kg: float
    currency: str
    packages_12kg: int
    packages_6kg: int
    additional_kg: int
    price_6kg: Decimal
    price_12kg: Decimal
    price_additional_kg: Decimal
    total: Decimal
    ruleset_version: str
    breakdown: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total_kg": self.total_kg,
            "currency": self.currency,
            "packages_12kg": self.packages_12kg,
            "packages_6kg": self.packages_6kg,
            "additional_kg": self.additional_kg,
            "total": float(self.total),
            "ruleset_version": self.ruleset_version,
            "breakdown": list(self.breakdown),
        }


def _price(code: str, market: str | None) -> Decimal:
    """Published price for a wash-fold code in a market, from the catalogue.
    Falls back to the AE base price only when the market has no overlay for it."""
    if market and catalogue.has_market_pricing(market):
        overlay = catalogue.market_prices(market)
        if code in overlay:
            return Decimal(str(overlay[code]))
    item = catalogue.item_by_code(code)
    if not item or item.get("current_price") is None:
        raise ValueError(f"wash-fold price missing for {code!r}")
    return Decimal(str(item["current_price"]))


def optimize_wash_fold(total_kg: float, *, market: str | None = "AE") -> WashFoldQuote:
    """Cheapest valid Wash & Fold price for ``total_kg``.

    Algorithm (matches the published examples): take as many full 12 kg packages as
    fit, then price the remainder as the cheapest of — additional kg on the last
    12 kg bag (only when a 12 kg bag exists and the bag stays within 20 kg), an extra
    6 kg package (remainder ≤ 6 kg), or an extra 12 kg package. A total below 6 kg
    still pays one 6 kg package.
    """
    if total_kg is None or total_kg <= 0:
        raise ValueError("total_kg must be positive")

    p6 = _price(_6KG, market)
    p12 = _price(_12KG, market)
    padd = _price(_ADDITIONAL_KG, market)
    currency = catalogue.market_currency(market) if market else catalogue.currency()
    ruleset = get_settings().whatsapp_service_ruleset_version

    def _quote(n12: int, n6: int, add_kg: int, total: Decimal) -> WashFoldQuote:
        lines: list[str] = []
        if n12:
            lines.append(f"{n12} x 12 kg package = {currency} {p12 * n12}")
        if n6:
            lines.append(f"{n6} x 6 kg package = {currency} {p6 * n6}")
        if add_kg:
            lines.append(f"{add_kg} additional kg x {currency} {padd} = {currency} {padd * add_kg}")
        return WashFoldQuote(
            total_kg=float(total_kg), currency=currency,
            packages_12kg=n12, packages_6kg=n6, additional_kg=add_kg,
            price_6kg=p6, price_12kg=p12, price_additional_kg=padd,
            total=total, ruleset_version=ruleset, breakdown=lines,
        )

    # A total at or below one 6 kg bag always pays exactly one 6 kg package.
    if total_kg <= 6:
        return _quote(0, 1, 0, p6)

    n12 = int(total_kg // _PKG_LIMIT_KG)
    remainder = total_kg - n12 * _PKG_LIMIT_KG  # 0 <= remainder < 12
    base = p12 * n12

    if remainder <= 0:
        return _quote(n12, 0, 0, base)

    # Additional weight is charged per whole kg (rounded up), on the last 12 kg bag.
    add_kg = math.ceil(remainder - 1e-9)
    candidates: list[WashFoldQuote] = []
    # Option A: extend the last 12 kg bag with additional kg (needs a 12 kg bag and
    # the bag must stay within the 20 kg physical limit).
    if n12 >= 1 and add_kg <= (_BAG_MAX_KG - _PKG_LIMIT_KG):
        candidates.append(_quote(n12, 0, add_kg, base + padd * add_kg))
    # Option B: an extra 6 kg package for the remainder (only when it fits a 6 kg bag).
    if remainder <= 6:
        candidates.append(_quote(n12, 1, 0, base + p6))
    # Option C: an extra 12 kg package for the remainder (always valid).
    candidates.append(_quote(n12 + 1, 0, 0, base + p12))

    return min(candidates, key=lambda q: q.total)
