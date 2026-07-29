"""Route-to-human (specialist) service classification (spec §2.8) — pure.

Some requests are NOT quoted by the agent at all — villa/home/deep cleaning,
wedding dresses, and luxury/bespoke garment care. For these the agent acknowledges
once, captures structured details, and hands off to a specialist team (a pending
task + human follow-up). This module decides whether a free-text request falls into
one of those categories, reading the terms/acknowledgements from
``config/specialty_routing.json`` (never hardcoded). Deterministic, offline.

Distinct from:
  * services.service_resolution UNSUPPORTED (politely declined, e.g. "haircut");
  * the §2.7 sell-directly specialty items (shoes/bags/carpets/curtains), which the
    agent DOES quote after a photo (the BESPOKE photo-quote flow);
  * B2B/commercial, handled by services/b2b.py + the escalation rules.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "specialty_routing.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_routing() -> None:
    """Drop the cache (tests / after a config edit)."""
    _raw.cache_clear()


def _categories() -> dict:
    return _raw().get("categories", {})


def categories() -> list[str]:
    return list(_categories().keys())


def is_valid_category(code: str | None) -> bool:
    return bool(code) and code in _categories()


def label(code: str) -> str:
    return _categories().get(code, {}).get("label", code)


def acknowledgement(code: str) -> str:
    return _categories().get(code, {}).get("acknowledgement",
                                           "Our specialist team will follow up with you shortly.")


def capture_fields(code: str) -> list[str]:
    return list(_categories().get(code, {}).get("capture", []))


@dataclass(frozen=True)
class RoutingMatch:
    category: str
    label: str
    matched_term: str


def classify(text: str | None) -> RoutingMatch | None:
    """The specialist category a request routes to, or None. First matching term
    wins (categories are checked in config order); matching is a case-insensitive
    substring on a whitespace-normalised message."""
    if not text:
        return None
    low = " ".join(str(text).lower().split())
    for code, cfg in _categories().items():
        for term in cfg.get("terms", []):
            if term.lower() in low:
                return RoutingMatch(category=code, label=cfg.get("label", code), matched_term=term)
    return None
