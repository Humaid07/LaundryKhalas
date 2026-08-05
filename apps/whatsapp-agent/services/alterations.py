"""Alteration price matrix resolver (spec §18) — pure & deterministic.

Maps an alteration request to the specific listed type and its price, applying the base /
pushback (haggle) / quantity tiers the spec defines. Generic or unlisted alterations
(basic hemming with no garment, a minor tear, generic tightening, lining repair) have NO
price and route to a facility quotation — the model never invents a price. Config-driven
(config/alterations.json); the backend is authoritative.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from settings import get_settings

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "alterations.json"

# The approved short reply when an alteration needs a facility quotation (spec §18).
FACILITY_QUOTE_REPLY = "Let me confirm the price for that and get back to you."


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_config() -> None:
    _config.cache_clear()


@dataclass(frozen=True)
class AlterationQuote:
    matched: bool               # True when the text is an alteration we recognise
    type_code: str | None
    name: str | None
    unit_price: float | None    # per item (or per button)
    quantity: int
    total: float | None
    facility_quote: bool        # True → priced by the facility, no number quoted
    currency: str
    rule_version: str


def _best_type(low: str) -> str | None:
    """Longest matching alias wins, so 'small zip my own' beats 'small zip'."""
    best, best_len = None, 0
    for code, t in _config()["types"].items():
        for alias in t["aliases"]:
            if alias in low and len(alias) > best_len:
                best, best_len = code, len(alias)
    return best


def resolve_alteration(text: str | None, *, quantity: int = 1, pushback: bool = False) -> AlterationQuote:
    """Resolve an alteration request to its price. ``quantity`` is the item count (buttons
    for BUTTON_REPLACE); ``pushback`` applies the haggle price where the type defines one."""
    cfg = _config()
    currency = cfg.get("currency", "AED")
    version = get_settings().whatsapp_service_ruleset_version
    quantity = max(1, int(quantity or 1))
    low = (text or "").lower()

    code = _best_type(low)
    if code:
        t = cfg["types"][code]
        # Quantity tier (best price) beats the pushback tier, which beats the base.
        if "quantity_price" in t and quantity >= t.get("quantity_threshold", 10 ** 9):
            unit = float(t["quantity_price"])
        elif pushback and "pushback" in t:
            unit = float(t["pushback"])
        else:
            unit = float(t["base"])
        total = round(unit * quantity, 2)
        return AlterationQuote(True, code, t["name"], unit, quantity, total, False, currency, version)

    # Unlisted alteration keywords → facility quotation (never invent a price).
    if any(k in low for k in cfg.get("facility_quote_keywords", [])):
        return AlterationQuote(True, None, None, None, quantity, None, True, currency, version)

    return AlterationQuote(False, None, None, None, quantity, None, False, currency, version)
