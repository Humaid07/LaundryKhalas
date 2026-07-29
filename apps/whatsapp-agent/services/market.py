"""Market / currency resolution (spec §8) — pure & deterministic.

Detects the customer's market from their WhatsApp phone number (E.164 country
prefix), maps it to a currency, and formats a customer-facing price string in that
currency. Guarantees the agent never mixes AED and QAR: a quote/link is always in
the market's own currency. ``pricing_configured`` tells callers whether a real
price list exists for the market — Qatar (QAR) is not yet priced, so QAR quotes
must route to a human rather than invent a number (CLAUDE.md §7/§8).

Config-driven (``config/markets.json``); money formatting via ``services.money``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from services import money

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "markets.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_markets() -> None:
    """Drop the cache (tests / after a config edit)."""
    _raw.cache_clear()


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    currency: str
    currency_prefix: str
    pricing_configured: bool


def default_market_code() -> str:
    return str(_raw().get("default_market", "AE"))


# Common spellings the customer/order records use → canonical market code, so a
# stored market of "UAE"/"Dubai"/"Qatar"/"Doha" resolves like it does in
# services/clock.py (which accepts the same aliases).
_ALIASES = {
    "ae": "AE", "uae": "AE", "u.a.e": "AE", "emirates": "AE", "dubai": "AE",
    "abu dhabi": "AE", "sharjah": "AE", "ajman": "AE",
    "qa": "QA", "qatar": "QA", "doha": "QA",
}


def _normalize_code(market_code: str | None) -> str:
    if not market_code:
        return default_market_code()
    raw = str(market_code).strip()
    markets = _raw().get("markets", {})
    if raw in markets:                       # exact code (e.g. "AE")
        return raw
    return _ALIASES.get(raw.lower(), default_market_code())


def get_market(market_code: str | None = None) -> Market:
    code = _normalize_code(market_code)
    markets = _raw().get("markets", {})
    m = markets.get(code)
    if m is None:
        code = default_market_code()
        m = markets.get(code, {})
    return Market(
        code=code,
        name=str(m.get("name", code)),
        currency=str(m.get("currency", "AED")),
        currency_prefix=str(m.get("currency_prefix", m.get("currency", "AED"))),
        pricing_configured=bool(m.get("pricing_configured", False)),
    )


def _digits(phone: str | None) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def market_for_phone(phone: str | None) -> Market:
    """Resolve a market from a customer's phone number by longest-matching country
    prefix. Falls back to the default market when no prefix matches (so the agent
    still quotes in a known currency rather than failing)."""
    digits = _digits(phone)
    markets = _raw().get("markets", {})
    best_code: str | None = None
    best_len = -1
    for code, m in markets.items():
        for prefix in m.get("phone_prefixes", []):
            p = _digits(prefix)
            if p and digits.startswith(p) and len(p) > best_len:
                best_code, best_len = code, len(p)
    return get_market(best_code)


def currency_for_phone(phone: str | None) -> str:
    return market_for_phone(phone).currency


def pricing_configured_for_phone(phone: str | None) -> bool:
    return market_for_phone(phone).pricing_configured


def format_price(amount, market_code: str | None = None) -> str:
    """Customer-facing price string in the market's currency, e.g. 'AED 60' or
    'QAR 52.50'. Uses ``money.format_money`` (whole numbers clean, else 2dp) and
    never emits VAT/tax wording."""
    m = get_market(market_code)
    return f"{m.currency_prefix} {money.format_money(amount)}"
