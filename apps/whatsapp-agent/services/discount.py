"""Automatic order-level discount engine (task spec §§5-11).

ONE place that decides whether an order qualifies for an automatic discount and
by how much. The rule (threshold, percentage, active) is loaded from
``config/order_discounts.json`` — never hardcoded across components (spec §5).

Contract:
  * The eligible subtotal is the sum of FINAL, VAT-inclusive line totals (the
    customer-facing money) — NOT an internal net figure.
  * The threshold comparison is STRICTLY GREATER THAN (spec §5): AED 100.00 →
    no discount; AED 100.01 → discount.
  * All money is Decimal, HALF-UP to 2dp (spec §6) via ``services.money``.
  * The discount is computed DETERMINISTICALLY from the current subtotal, so
    recomputing (duplicate webhook, order reopen, summary regen) yields the same
    result and never stacks/compounds (spec §9).
  * When the exact total is unknown (a 'from'/inspection/measured line is
    present), NO guaranteed discount is applied — the caller passes
    ``total_is_known=False`` (spec §8).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services import money

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "order_discounts.json"


@dataclass(frozen=True)
class DiscountRule:
    rule_code: str
    name: str
    threshold_amount: Decimal
    discount_percentage: Decimal      # e.g. Decimal('15') for 15%
    currency: str
    active: bool
    stacking: str

    @property
    def discount_fraction(self) -> Decimal:
        return self.discount_percentage / Decimal(100)


@dataclass(frozen=True)
class DiscountResult:
    """Outcome of evaluating the automatic discount for one order subtotal."""
    applied: bool
    reason: str                       # applied | below_threshold | unknown_total | inactive | no_rule
    rule_code: str | None
    eligible_subtotal: Decimal
    threshold: Decimal | None
    discount_percentage: Decimal | None   # snapshot, e.g. 15
    discount_amount: Decimal              # 0.00 when not applied
    final_total: Decimal                  # subtotal - discount_amount

    def to_snapshot(self) -> dict:
        """Immutable snapshot fields for the order row (spec §11). Floats for the
        numeric(12,2) columns; the customer-facing money already rounded."""
        return {
            "discount_rule_code": self.rule_code if self.applied else None,
            "discount_threshold": float(self.threshold) if self.threshold is not None else None,
            "discount_percentage": float(self.discount_percentage) if self.discount_percentage is not None else None,
            "discount_amount": float(self.discount_amount),
            "eligible_subtotal": float(self.eligible_subtotal),
            "final_total": float(self.final_total),
        }


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_rules() -> None:
    """Drop the cache (tests / after a config edit)."""
    clear = getattr(_raw, "cache_clear", None)
    if clear:
        clear()


def active_rule(*, market: str = "AE") -> DiscountRule | None:
    """The single active automatic order-discount rule for a market, or None.

    First active rule whose ``eligible_markets`` includes the market wins; the
    config currently defines exactly one (ORDER_OVER_100_DISCOUNT)."""
    for r in _raw().get("rules", []):
        if not r.get("active", False):
            continue
        markets = r.get("eligible_markets")
        if markets and market not in markets:
            continue
        return DiscountRule(
            rule_code=r["rule_code"],
            name=r.get("name", r["rule_code"]),
            threshold_amount=money.to_decimal(r["threshold_amount"]),
            discount_percentage=money.to_decimal(r["discount_value"]),
            currency=r.get("currency", "AED"),
            active=True,
            stacking=r.get("stacking", "non_stackable"),
        )
    return None


def evaluate(eligible_subtotal, *, total_is_known: bool = True,
             market: str = "AE") -> DiscountResult:
    """Evaluate the automatic order discount for ``eligible_subtotal``.

    ``eligible_subtotal`` is the sum of FINAL VAT-inclusive line totals. When
    ``total_is_known`` is False (a 'from'/inspection/measured line makes the
    exact total unknown) no guaranteed discount is applied (spec §8).
    """
    subtotal = money.round_money(eligible_subtotal)
    rule = active_rule(market=market)

    if rule is None:
        return DiscountResult(False, "no_rule", None, subtotal, None, None,
                              money.round_money(0), subtotal)
    if not total_is_known:
        return DiscountResult(False, "unknown_total", None, subtotal,
                              rule.threshold_amount, None, money.round_money(0), subtotal)
    # STRICT greater-than (spec §5): exactly-at-threshold does NOT qualify.
    if subtotal <= rule.threshold_amount:
        return DiscountResult(False, "below_threshold", None, subtotal,
                              rule.threshold_amount, None, money.round_money(0), subtotal)

    discount_amount = money.round_money(subtotal * rule.discount_fraction)
    final_total = money.round_money(subtotal - discount_amount)
    return DiscountResult(
        applied=True, reason="applied", rule_code=rule.rule_code,
        eligible_subtotal=subtotal, threshold=rule.threshold_amount,
        discount_percentage=rule.discount_percentage,
        discount_amount=discount_amount, final_total=final_total,
    )
