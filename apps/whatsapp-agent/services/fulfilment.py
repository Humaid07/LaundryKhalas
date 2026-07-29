"""Minimum-order + pickup/delivery-charge engine (spec §2.3) — pure & deterministic.

Free pickup & delivery when the eligible order total is at or above the market's
``free_delivery_min`` (default 50); otherwise a single flat ``delivery_fee``
(default 8) applies and must be stated up front. Config-driven
(``config/fulfilment_charges.json``); all money is Decimal via ``services.money``.
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
        free_delivery_min=money.to_decimal(m.get("free_delivery_min", 50)),
        delivery_fee=money.to_decimal(m.get("delivery_fee", 8)),
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


def delivery_charge(order_total, *, market: str = "AE") -> DeliveryCharge:
    """The pickup/delivery charge for an order total. Free at or above the market's
    minimum; otherwise the flat fee. ``order_total`` is the sum of final,
    VAT-inclusive line totals BEFORE any delivery fee."""
    cfg = charges_for(market)
    total = money.round_money(order_total)
    if total >= cfg.free_delivery_min:
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
