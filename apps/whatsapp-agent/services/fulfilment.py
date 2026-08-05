"""Minimum-order + pickup/delivery-charge engine (spec §12) — pure & deterministic.

Free pickup & delivery when the SERVICE SUBTOTAL BEFORE DISCOUNT is at or above the
market's ``free_delivery_min`` (ruleset 2026_08_05: AED/QAR 30); otherwise we ask the
customer to add an item and, if they decline, a single flat ``delivery_fee``
(AED/QAR 10) applies and must be stated up front — never disguised as a service price.
Config-driven (``config/fulfilment_charges.json``); all money is Decimal via
``services.money``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services import money

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "fulfilment_charges.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_charges() -> None:
    """Drop the cache (tests / after a config edit)."""
    _raw.cache_clear()


@dataclass(frozen=True)
class MarketCharges:
    currency: str
    free_delivery_min: Decimal
    delivery_fee: Decimal


def charges_for(market: str = "AE") -> MarketCharges:
    markets = _raw().get("markets", {})
    m = markets.get(market) or next(iter(markets.values()), {})
    return MarketCharges(
        currency=str(m.get("currency", "AED")),
        free_delivery_min=money.to_decimal(m.get("free_delivery_min", 30)),
        delivery_fee=money.to_decimal(m.get("delivery_fee", 10)),
    )


@dataclass(frozen=True)
class DeliveryCharge:
    free: bool
    fee: Decimal                 # 0.00 when free
    currency: str
    free_delivery_min: Decimal
    order_total: Decimal
    order_grand_total: Decimal   # order_total + fee

    def to_snapshot(self) -> dict:
        return {
            "delivery_free": self.free,
            "delivery_fee": float(self.fee),
            "currency": self.currency,
            "free_delivery_min": float(self.free_delivery_min),
            "order_total": float(self.order_total),
            "order_grand_total": float(self.order_grand_total),
        }


def delivery_charge(order_total, *, market: str = "AE", threshold_total=None) -> DeliveryCharge:
    """The pickup/delivery charge for an order. Free at or above the market's minimum;
    otherwise the flat fee.

    ``order_total`` is the payable sum of final, VAT-inclusive line totals BEFORE any
    delivery fee — the fee is added to it for ``order_grand_total``.

    ``threshold_total`` is the value compared against the free-delivery minimum. When
    given it is the SERVICE SUBTOTAL BEFORE DISCOUNT (spec §12: the minimum is judged on
    the pre-discount subtotal so a discount never pushes an order below the threshold);
    when omitted it defaults to ``order_total`` (backward compatible)."""
    cfg = charges_for(market)
    total = money.round_money(order_total)
    threshold = money.round_money(order_total if threshold_total is None else threshold_total)
    if threshold >= cfg.free_delivery_min:
        fee = money.round_money(0)
        free = True
    else:
        fee = money.round_money(cfg.delivery_fee)
        free = False
    return DeliveryCharge(
        free=free, fee=fee, currency=cfg.currency,
        free_delivery_min=cfg.free_delivery_min, order_total=total,
        order_grand_total=money.round_money(total + fee),
    )


@dataclass(frozen=True)
class MinimumOrderStatus:
    """Whether an order's pre-discount service subtotal is below the free-delivery
    minimum, and the deterministic figures needed to talk about it."""
    below_minimum: bool
    subtotal: Decimal
    minimum: Decimal
    delivery_fee: Decimal
    currency: str


def evaluate_minimum_order(subtotal_before_discount, *, market: str = "AE") -> MinimumOrderStatus:
    """Judge the minimum-order threshold on the SERVICE SUBTOTAL BEFORE DISCOUNT
    (spec §12). Never rejects the order — below the minimum the flow asks the
    customer to add an item, and applies ``delivery_fee`` only if they decline."""
    cfg = charges_for(market)
    subtotal = money.round_money(subtotal_before_discount)
    return MinimumOrderStatus(
        below_minimum=subtotal < cfg.free_delivery_min,
        subtotal=subtotal, minimum=cfg.free_delivery_min,
        delivery_fee=cfg.delivery_fee, currency=cfg.currency,
    )


def minimum_order_add_item_text(market: str = "AE") -> str:
    """MINIMUM_ORDER_ADD_ITEM template (spec §§12, 26). Short, no emoji/exclamation/dash;
    currency + amount come from config so wording can never drift from the rule."""
    cfg = charges_for(market)
    return (f"The minimum for free pickup and delivery is {cfg.currency} "
            f"{money.format_money(cfg.free_delivery_min)}. Would you like to add another item?")


def minimum_order_delivery_fee_text(market: str = "AE") -> str:
    """MINIMUM_ORDER_DELIVERY_FEE template (spec §§12, 26): the customer declined to add
    an item, so we continue and state the flat delivery charge up front."""
    cfg = charges_for(market)
    return (f"No problem. We can continue, and the delivery charge will be "
            f"{cfg.currency} {money.format_money(cfg.delivery_fee)}.")
