"""Automatic order-level discount engine (task spec §§5-11 + discount precedence).

ONE place that decides whether an order qualifies for an automatic discount and
by how much. The rules (thresholds, percentages, active state) are loaded from
``config/order_discounts.json`` — never hardcoded across components.

Precedence (a SINGLE discount is ever applied — the tiers NEVER stack):
  * If the customer explicitly asked for a discount AND the exact pre-discount
    subtotal is strictly greater than AED 200 → 20%.
  * Otherwise, if the exact pre-discount subtotal is strictly greater than
    AED 100 → 15%.
  * Otherwise → no order-level discount.

Both thresholds are STRICTLY greater-than: AED 100.00 → none; AED 200.00 with a
request → 15% (not 20%, since 200 is not > 200); AED 200.01 with a request → 20%.

Contract:
  * The eligible subtotal is the sum of FINAL, VAT-inclusive line totals.
  * All money is Decimal, HALF-UP to 2dp via ``services.money``.
  * Deterministic: recomputing the same (subtotal, discount_requested) yields the
    same result and never stacks/compounds (spec §9).
  * When the exact total is unknown (a 'from'/inspection/measured/bespoke line),
    NO guaranteed discount is applied — the caller passes ``total_is_known=False``.
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
    discount_percentage: Decimal          # e.g. Decimal('15') for 15%
    currency: str
    active: bool
    stacking: str
    requires_discount_request: bool       # 20% tier only applies when the customer asked
    priority: int                         # higher wins when >1 rule qualifies
    version: str

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
    discount_percentage: Decimal | None
    discount_amount: Decimal
    final_total: Decimal
    discount_requested: bool = False
    rule_version: str | None = None

    def to_snapshot(self) -> dict:
        """Immutable snapshot fields for the order row (spec §11). Changing a rule
        later never alters this frozen record."""
        return {
            "discount_rule_code": self.rule_code if self.applied else None,
            "discount_threshold": float(self.threshold) if self.threshold is not None else None,
            "discount_percentage": float(self.discount_percentage) if self.discount_percentage is not None else None,
            "discount_amount": float(self.discount_amount),
            "eligible_subtotal": float(self.eligible_subtotal),
            "final_total": float(self.final_total),
            "discount_requested": self.discount_requested,
            "discount_rule_version": self.rule_version,
        }


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_rules() -> None:
    """Drop the cache (tests / after a config edit)."""
    clear = getattr(_raw, "cache_clear", None)
    if clear:
        clear()


def _all_rules(*, market: str = "AE") -> list[DiscountRule]:
    out: list[DiscountRule] = []
    for r in _raw().get("rules", []):
        if not r.get("active", False):
            continue
        markets = r.get("eligible_markets")
        if markets and market not in markets:
            continue
        out.append(DiscountRule(
            rule_code=r["rule_code"],
            name=r.get("name", r["rule_code"]),
            threshold_amount=money.to_decimal(r["threshold_amount"]),
            discount_percentage=money.to_decimal(r["discount_value"]),
            currency=r.get("currency", "AED"),
            active=True,
            stacking=r.get("stacking", "non_stackable"),
            requires_discount_request=bool(r.get("requires_discount_request", False)),
            priority=int(r.get("priority", 0)),
            version=str(r.get("version", "1")),
        ))
    return out


def resolve_rule(eligible_subtotal, *, discount_requested: bool = False,
                 market: str = "AE") -> DiscountRule | None:
    """The SINGLE order-level rule that applies to ``eligible_subtotal`` under the
    precedence, or None. A rule qualifies when it is active, its (strict) threshold
    is exceeded, and — for a request-only rule — the customer actually asked for a
    discount. Among qualifiers, the highest ``priority`` wins so the 20% tier
    beats the 15% tier without ever stacking."""
    subtotal = money.round_money(eligible_subtotal)
    candidates = [
        r for r in _all_rules(market=market)
        if subtotal > r.threshold_amount
        and (discount_requested or not r.requires_discount_request)
    ]
    if not candidates:
        return None
    # highest priority, then highest percentage as a stable tiebreak
    return max(candidates, key=lambda r: (r.priority, r.discount_percentage))


def evaluate(eligible_subtotal, *, total_is_known: bool = True,
             discount_requested: bool = False, market: str = "AE") -> DiscountResult:
    """Evaluate the single applicable automatic order discount.

    ``eligible_subtotal`` is the sum of FINAL VAT-inclusive line totals. When
    ``total_is_known`` is False (unknown exact total) no guaranteed discount is
    applied (spec §8). ``discount_requested`` gates the 20%-over-200 tier.
    """
    subtotal = money.round_money(eligible_subtotal)
    zero = money.round_money(0)

    if not total_is_known:
        return DiscountResult(False, "unknown_total", None, subtotal, None, None,
                              zero, subtotal, discount_requested, None)

    rule = resolve_rule(subtotal, discount_requested=discount_requested, market=market)
    if rule is None:
        reason = "below_threshold" if _all_rules(market=market) else "no_rule"
        return DiscountResult(False, reason, None, subtotal, None, None,
                              zero, subtotal, discount_requested, None)

    discount_amount = money.round_money(subtotal * rule.discount_fraction)
    final_total = money.round_money(subtotal - discount_amount)
    return DiscountResult(
        applied=True, reason="applied", rule_code=rule.rule_code,
        eligible_subtotal=subtotal, threshold=rule.threshold_amount,
        discount_percentage=rule.discount_percentage,
        discount_amount=discount_amount, final_total=final_total,
        discount_requested=discount_requested, rule_version=rule.version,
    )


# --------------------------------------------------------------------------
# Natural-language discount-request detection (spec: recognise "make it cheaper",
# "best rate", "that's expensive", "any offers", etc. -> discount_requested=true)
# --------------------------------------------------------------------------
_DISCOUNT_PHRASES = (
    "discount", "cheaper", "cheapest", "best rate", "best price", "better price",
    "better rate", "lower price", "lower rate", "reduce the price", "reduce price",
    "good rate", "good price", "special price", "special rate", "any offer",
    "any offers", "offer", "deal", "promo", "promotion", "too expensive",
    "so expensive", "quite expensive", "very expensive", "thats expensive",
    "that is expensive", "can you do better", "do better on", "less expensive",
    "make it cheaper", "cheaper rate", "cheaper price", "better deal", "reduce it",
)


def detect_discount_request(text: str | None) -> bool:
    """True when the customer is asking for a discount / a better rate. Phrase
    match on a punctuation-normalised message; deliberately broad but anchored to
    price-negotiation language so ordinary requests never trip it."""
    if not text:
        return False
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    low = f" {' '.join(cleaned.split())} "
    return any(f" {p} " in low for p in _DISCOUNT_PHRASES)
