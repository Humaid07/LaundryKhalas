"""Price-negotiation engine (founder-approved spec §3) — pure & deterministic.

The agent ALWAYS quotes the website/database baseline price first (spec §2.1).
This engine is the ONLY sanctioned way to move off that baseline, and it is only
ever engaged when the customer haggles / asks for a discount. It never runs
automatically — that is the difference from ``services.discount`` (named/auto
promos), which the negotiation-only model retires from the happy path.

Two mechanisms, both loaded from ``config/negotiation.json`` (never hardcoded):

  1. Standard ladder (§3.1). Two tiers keyed off the order subtotal:
       * subtotal  < tier_threshold (default 100) → low ladder  (default 10% → 20%)
       * subtotal >= tier_threshold               → high ladder (default 15% → 25%)
     The first step is offered; if the customer rejects it OR ghosts (no reply for
     more than ``ghost_timeout_seconds``) the next step — the tier's standard
     maximum — is offered. The ladder never stacks: each step is a fresh discount
     off the ORIGINAL subtotal, not off the previous offer.

  2. Facility-floor (§3.2/§3.3). Only after the standard maximum, and only once the
     customer has fully itemised the order (so the backend can look up a real
     facility cost), the agent may concede at most ``max_concession_fraction``
     (default 0.75) of the gap between the already-discounted price and the closest
     facility cost:

         floor = discounted - max_concession_fraction × (discounted - facility_cost)

     The floor is a HARD limit; anything a customer demands below it → escalate to a
     human (handled by the caller). The raw facility cost is NEVER surfaced — only
     the floor price is returned to the model (CLAUDE.md §7).

Contract:
  * All money is Decimal, HALF-UP to 2dp via ``services.money``.
  * Deterministic: same inputs → same result; ladder steps never compound.
  * This module computes; it does NOT thread conversation timing or decide when to
    escalate — the orchestration layer (webhook/booking tools) owns that and passes
    the current step / ghost seconds / itemisation flag / facility cost in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services import money

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "negotiation.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_policy() -> None:
    """Drop the cache (tests / after a config edit)."""
    _raw.cache_clear()


@dataclass(frozen=True)
class NegotiationPolicy:
    active: bool
    version: str
    currency: str
    tier_threshold: Decimal
    low_ladder: tuple[Decimal, ...]
    high_ladder: tuple[Decimal, ...]
    ghost_timeout_seconds: int
    max_concession_fraction: Decimal
    itemisation_required_for_floor: bool


def load_policy(*, market: str = "AE") -> NegotiationPolicy:
    """The negotiation policy for a market. Unknown markets fall back to the first
    configured market so the engine never invents numbers."""
    raw = _raw()
    markets = raw.get("markets", {})
    m = markets.get(market) or next(iter(markets.values()), {})
    return NegotiationPolicy(
        active=bool(raw.get("active", False)),
        version=str(raw.get("version", "1")),
        currency=str(m.get("currency", "AED")),
        tier_threshold=money.to_decimal(m.get("tier_threshold", 100)),
        low_ladder=tuple(money.to_decimal(p) for p in m.get("low_ladder_percentages", [])),
        high_ladder=tuple(money.to_decimal(p) for p in m.get("high_ladder_percentages", [])),
        ghost_timeout_seconds=int(raw.get("ghost_timeout_seconds", 300)),
        max_concession_fraction=money.to_decimal(raw.get("max_concession_fraction", 0.75)),
        itemisation_required_for_floor=bool(raw.get("itemisation_required_for_floor", True)),
    )


# --------------------------------------------------------------------------
# Tier / ladder
# --------------------------------------------------------------------------
def tier_for(subtotal, *, policy: NegotiationPolicy | None = None) -> str:
    """'low' when subtotal < tier_threshold, else 'high' (boundary is inclusive of
    the high tier, matching 'order >= 100' in the spec)."""
    policy = policy or load_policy()
    return "high" if money.round_money(subtotal) >= policy.tier_threshold else "low"


def ladder_for(subtotal, *, policy: NegotiationPolicy | None = None) -> tuple[Decimal, ...]:
    policy = policy or load_policy()
    return policy.high_ladder if tier_for(subtotal, policy=policy) == "high" else policy.low_ladder


def standard_max_percentage(subtotal, *, policy: NegotiationPolicy | None = None) -> Decimal | None:
    """The deepest STANDARD discount for the tier (20% low / 25% high), or None if
    the tier has no ladder configured."""
    ladder = ladder_for(subtotal, policy=policy)
    return ladder[-1] if ladder else None


def is_ghosted(seconds_since_last_customer_message, *,
               policy: NegotiationPolicy | None = None) -> bool:
    """A customer has 'ghosted' when they have not replied for MORE than the
    configured window (default 5 minutes). Used by the orchestrator to decide
    whether to advance the ladder to the next step (§3.1)."""
    policy = policy or load_policy()
    if seconds_since_last_customer_message is None:
        return False
    return float(seconds_since_last_customer_message) > policy.ghost_timeout_seconds


def _discounted_price(subtotal: Decimal, percentage: Decimal) -> Decimal:
    return money.round_money(subtotal * (Decimal(1) - percentage / Decimal(100)))


@dataclass(frozen=True)
class LadderOffer:
    """One rung of the standard ladder for a given order subtotal."""
    reason: str                     # offered | exhausted | inactive | invalid
    step: int
    tier: str
    percentage: Decimal | None      # None → nothing to offer at this step
    original_subtotal: Decimal
    price: Decimal | None
    is_standard_max: bool           # True when this rung is the tier's deepest standard offer
    exhausted: bool                 # True when the ladder is spent → floor/escalate path

    def to_snapshot(self) -> dict:
        """Loggable record of the offer (spec §3.4 — log every offer)."""
        return {
            "kind": "ladder_offer",
            "reason": self.reason,
            "step": self.step,
            "tier": self.tier,
            "percentage": float(self.percentage) if self.percentage is not None else None,
            "original_subtotal": float(self.original_subtotal),
            "offered_price": float(self.price) if self.price is not None else None,
            "is_standard_max": self.is_standard_max,
            "exhausted": self.exhausted,
        }


def ladder_offer(subtotal, step: int, *,
                 policy: NegotiationPolicy | None = None) -> LadderOffer:
    """The discount to offer at 0-indexed ``step`` of the standard ladder.

    ``step`` is advanced by the orchestrator each time the customer rejects the
    prior rung OR ghosts past the window. When ``step`` runs past the ladder the
    result is ``exhausted`` (the caller then either goes to the facility-floor once
    the order is itemised, or escalates to a human)."""
    policy = policy or load_policy()
    subtotal_d = money.round_money(subtotal)

    if not policy.active:
        return LadderOffer("inactive", step, "n/a", None, subtotal_d, None, False, False)
    if subtotal_d <= 0 or step < 0:
        return LadderOffer("invalid", step, "n/a", None, subtotal_d, None, False, False)

    tier = tier_for(subtotal_d, policy=policy)
    ladder = ladder_for(subtotal_d, policy=policy)

    if not ladder or step >= len(ladder):
        return LadderOffer("exhausted", step, tier, None, subtotal_d, None, False, True)

    percentage = ladder[step]
    price = _discounted_price(subtotal_d, percentage)
    return LadderOffer(
        reason="offered", step=step, tier=tier, percentage=percentage,
        original_subtotal=subtotal_d, price=price,
        is_standard_max=(step == len(ladder) - 1), exhausted=False,
    )


# --------------------------------------------------------------------------
# Facility-floor (§3.2 / §3.3)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FloorOffer:
    """The deepest price the agent may reach via facility-floor negotiation."""
    allowed: bool
    reason: str                     # ok | no_room | needs_itemisation | no_facility_cost | inactive
    discounted_price: Decimal
    facility_cost: Decimal | None   # backend-only, NEVER surfaced to model/customer
    concession_fraction: Decimal
    max_concession: Decimal | None
    floor_price: Decimal | None
    margin_above_cost: Decimal | None

    def to_snapshot(self) -> dict:
        """Loggable record. Includes the consulted facility cost for the AUDIT log
        only (spec §3.4). Callers must NOT put this on any customer/facility-facing
        channel — surface ``floor_price`` alone."""
        return {
            "kind": "facility_floor",
            "allowed": self.allowed,
            "reason": self.reason,
            "discounted_price": float(self.discounted_price),
            "facility_cost": float(self.facility_cost) if self.facility_cost is not None else None,
            "concession_fraction": float(self.concession_fraction),
            "max_concession": float(self.max_concession) if self.max_concession is not None else None,
            "floor_price": float(self.floor_price) if self.floor_price is not None else None,
            "margin_above_cost": float(self.margin_above_cost) if self.margin_above_cost is not None else None,
        }


def facility_floor(discounted_price, facility_cost, *, itemised: bool,
                   policy: NegotiationPolicy | None = None) -> FloorOffer:
    """Compute the absolute floor once the standard ladder is spent (§3.2).

    ``discounted_price`` is the price already reached at the standard maximum.
    ``facility_cost`` is the closest facility cost for the itemised order (looked up
    backend-side). Concedes at most ``max_concession_fraction`` of the gap:

        floor = discounted - fraction × (discounted - facility_cost)

    Guards:
      * ``itemised`` must be True (spec §3.3 itemisation guard) — without a full item
        list the backend cannot compute a real facility cost, so the agent cannot go
        below the standard ladder.
      * A missing / non-positive facility cost → not allowed (never guess a cost).
      * When the facility cost already meets/exceeds the discounted price there is no
        room to concede — the floor is the discounted price itself (reason 'no_room').
    """
    policy = policy or load_policy()
    disc = money.round_money(discounted_price)
    fraction = policy.max_concession_fraction

    if not policy.active:
        return FloorOffer(False, "inactive", disc, None, fraction, None, None, None)
    if policy.itemisation_required_for_floor and not itemised:
        return FloorOffer(False, "needs_itemisation", disc, None, fraction, None, None, None)
    if facility_cost is None or money.to_decimal(facility_cost) <= 0:
        return FloorOffer(False, "no_facility_cost", disc, None, fraction, None, None, None)

    cost = money.round_money(facility_cost)
    if cost >= disc:
        # No margin room to give away — hold at the already-discounted price.
        return FloorOffer(True, "no_room", disc, cost, fraction,
                          money.round_money(0), disc, money.round_money(disc - cost))

    gap = disc - cost
    max_concession = money.round_money(gap * fraction)
    floor = money.round_money(disc - max_concession)
    return FloorOffer(
        allowed=True, reason="ok", discounted_price=disc, facility_cost=cost,
        concession_fraction=fraction, max_concession=max_concession,
        floor_price=floor, margin_above_cost=money.round_money(floor - cost),
    )


# --------------------------------------------------------------------------
# Orchestration helper: what to offer NEXT given the persisted state
# --------------------------------------------------------------------------
def _index_of(ladder: tuple[Decimal, ...], pct: Decimal) -> int | None:
    for i, p in enumerate(ladder):
        if p == pct:
            return i
    return None


def _pct_off(subtotal: Decimal, price: Decimal) -> Decimal:
    if subtotal <= 0:
        return money.round_money(0)
    return money.round_money((subtotal - price) / subtotal * Decimal(100))


@dataclass(frozen=True)
class NegotiationDecision:
    """What the agent should offer NEXT for an order, given what it already offered.

    ``action``:
      * offer_ladder    — offer ``percentage`` off (``price`` is the new total)
      * offer_floor     — offer the facility-floor ``price`` (deepest possible)
      * ask_itemisation — need the full item list before a deeper (floor) price
      * escalate        — nothing more the agent may offer → hand to a human
      * inactive/invalid
    """
    action: str
    percentage: Decimal | None
    price: Decimal | None
    original_subtotal: Decimal
    is_standard_max: bool
    rule_code: str | None            # persisted marker: NEGOTIATED | NEG_FLOOR
    reason: str

    def to_snapshot(self) -> dict:
        return {
            "kind": "negotiation_decision",
            "action": self.action,
            "percentage": float(self.percentage) if self.percentage is not None else None,
            "price": float(self.price) if self.price is not None else None,
            "original_subtotal": float(self.original_subtotal),
            "is_standard_max": self.is_standard_max,
            "rule_code": self.rule_code,
            "reason": self.reason,
        }


def plan_offer(subtotal, *, current_percentage=None, current_rule_code: str | None = None,
               itemised: bool = False, facility_cost=None,
               policy: NegotiationPolicy | None = None) -> NegotiationDecision:
    """Decide the next negotiation move for an order.

    ``current_percentage`` / ``current_rule_code`` are what is already persisted on
    the order (None → nothing offered yet). Each call advances one rung — the agent
    calls this whenever the customer is still pushing (rejection); the 5-minute
    ghost auto-advance is an orchestration concern handled by the caller. Once the
    standard ladder is spent, the facility-floor is offered when the order is fully
    itemised and a ``facility_cost`` is available; otherwise the agent escalates.
    """
    policy = policy or load_policy()
    sub = money.round_money(subtotal)

    if not policy.active:
        return NegotiationDecision("inactive", None, None, sub, False, None, "inactive")
    if sub <= 0:
        return NegotiationDecision("invalid", None, None, sub, False, None, "invalid")
    if current_rule_code == "NEG_FLOOR":
        # Already at the absolute floor — any further ask is below it → human.
        return NegotiationDecision("escalate", None, None, sub, False, None, "below_floor")

    ladder = ladder_for(sub, policy=policy)
    if not ladder:
        return NegotiationDecision("escalate", None, None, sub, False, None, "no_ladder")

    if current_percentage is None:
        step = 0
    else:
        cur = money.to_decimal(current_percentage)
        idx = _index_of(ladder, cur)
        step = (idx + 1) if idx is not None else (len(ladder) if cur >= ladder[-1] else 1)

    if step < len(ladder):
        pct = ladder[step]
        return NegotiationDecision(
            "offer_ladder", pct, _discounted_price(sub, pct), sub,
            step == len(ladder) - 1, "NEGOTIATED", "offered")

    # Standard ladder spent → facility-floor (§3.2/§3.3).
    standard_max = ladder[-1]
    discounted = _discounted_price(sub, standard_max)
    floor = facility_floor(discounted, facility_cost, itemised=itemised, policy=policy)
    if floor.allowed and floor.floor_price is not None:
        return NegotiationDecision(
            "offer_floor", _pct_off(sub, floor.floor_price), floor.floor_price, sub,
            False, "NEG_FLOOR", floor.reason)
    if floor.reason == "needs_itemisation":
        return NegotiationDecision("ask_itemisation", None, None, sub, False, None, "needs_itemisation")
    return NegotiationDecision("escalate", None, None, sub, False, None, floor.reason)
