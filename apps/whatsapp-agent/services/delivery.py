"""Deterministic delivery SLA / turnaround + Express eligibility engine.

Given the catalogue items on an order, this computes each item's turnaround
rule, whether the whole order is Express-eligible, and the order-level delivery
estimate off the pickup end time. Rules are DB-driven (config/delivery_sla.json →
`delivery_sla_rules`); this module reads the cached JSON (the seed keeps the DB in
lockstep), mirroring services/catalogue.py.

Contract (task spec §§23-25, CLAUDE.md §5/§8):
  * SLA is data, never invented by the LLM. Unknown items fall back to the safe
    default rule (1–2 days) — never a fabricated exact hour.
  * A combined order uses the SLOWEST applicable rule (largest max_hours).
  * Express = 12h, offered ONLY when EVERY item is Express-eligible. Its surcharge
    is not invented here (meta.express_surcharge_aed is null until configured).
  * 'days' = CALENDAR days by default (meta.day_type); working-day math is a
    documented follow-up, not silently assumed in a prompt.
"""
from __future__ import annotations

import datetime as _dt
import json
from functools import lru_cache
from pathlib import Path

from services import catalogue

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_SLA_FILE = "delivery_sla.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads((_CONFIG_DIR / _SLA_FILE).read_text(encoding="utf-8"))


def reload_sla() -> None:
    _raw.cache_clear()


def meta() -> dict:
    return _raw()["meta"]


def express_hours() -> int:
    return int(meta().get("express_hours", 12))


def express_eligible_categories() -> set[str]:
    return set(meta().get("express_eligible_categories", []))


def rules() -> list[dict]:
    return _raw()["rules"]


def default_rule() -> dict:
    return _raw()["default_rule"]


def sla_for_item(item_code: str) -> dict:
    """The most-specific SLA rule for an item: an item-level rule wins over its
    category default, which wins over the global default. Returns a rule dict."""
    item = catalogue.item_by_code(item_code)
    category_code = item["category_code"] if item else None
    best = None
    for rule in rules():
        m = rule.get("match", {})
        if item_code in (m.get("item_codes") or []):
            if best is None or rule.get("priority", 0) > best.get("priority", 0):
                best = rule
        elif category_code and m.get("category_code") == category_code:
            if best is None or rule.get("priority", 0) > best.get("priority", 0):
                best = rule
    return best or default_rule()


def _is_express_eligible(item_code: str, rule: dict) -> bool:
    item = catalogue.item_by_code(item_code)
    cat = item["category_code"] if item else None
    return bool(rule.get("express_eligible")) and cat in express_eligible_categories()


def order_turnaround(item_codes: list[str], *, express: bool = False) -> dict:
    """Combined turnaround for an order. Uses the SLOWEST item rule (largest
    max_hours). ``express_eligible`` is True only when EVERY item is eligible;
    ``applied_express`` is True only when Express was requested AND the whole
    order is eligible (then the turnaround collapses to the Express window)."""
    codes = [c for c in (item_codes or []) if c]
    if not codes:
        d = default_rule()
        return {
            "min_hours": d["min_hours"], "max_hours": d["max_hours"],
            "day_type": d.get("day_type", "CALENDAR"), "display_text": d["display_text"],
            "rule_codes": [], "express_eligible": False, "applied_express": False,
        }
    per_item = [(c, sla_for_item(c)) for c in codes]
    express_eligible = all(_is_express_eligible(c, r) for c, r in per_item)

    if express and express_eligible:
        h = express_hours()
        return {
            "min_hours": h, "max_hours": h, "day_type": "CALENDAR",
            "display_text": f"{h} hours (Express)",
            "rule_codes": ["EXPRESS"], "express_eligible": True, "applied_express": True,
        }

    # Slowest rule = largest max_hours, tie-break by largest min_hours.
    slowest = max((r for _, r in per_item),
                  key=lambda r: (r["max_hours"], r["min_hours"]))
    return {
        "min_hours": slowest["min_hours"], "max_hours": slowest["max_hours"],
        "day_type": slowest.get("day_type", "CALENDAR"),
        "display_text": slowest["display_text"],
        "rule_codes": sorted({r["code"] for _, r in per_item}),
        "express_eligible": express_eligible, "applied_express": False,
    }


def estimate_delivery(item_codes: list[str], pickup_end_at: _dt.datetime | None,
                      *, express: bool = False) -> dict:
    """Order-level delivery estimate. Adds the turnaround window to the pickup end
    time (CALENDAR hours). ``pickup_end_at`` None → no dated estimate, only the
    turnaround text (never a fabricated hour)."""
    t = order_turnaround(item_codes, express=express)
    start_at = end_at = None
    if pickup_end_at is not None:
        start_at = pickup_end_at + _dt.timedelta(hours=t["min_hours"])
        end_at = pickup_end_at + _dt.timedelta(hours=t["max_hours"])
    return {
        **t,
        "estimated_delivery_start_at": start_at,
        "estimated_delivery_end_at": end_at,
        "estimated_delivery_text": _delivery_text(t, start_at, end_at),
    }


def _delivery_text(t: dict, start_at, end_at) -> str:
    """A customer-facing delivery line, e.g. 'Saturday, 25 July 2026' or
    'Estimated turnaround: 2–3 days'. Never converts a range into a guarantee."""
    if end_at is None:
        return f"Estimated turnaround: {t['display_text']}"
    if start_at and start_at.date() != end_at.date():
        return f"{start_at.strftime('%a, %d %B')} – {end_at.strftime('%a, %d %B %Y')}"
    return end_at.strftime("%A, %d %B %Y")


def delivery_options(item_codes: list[str]) -> dict:
    """Standard + (when eligible) Express options for the delivery-mode step."""
    std = order_turnaround(item_codes, express=False)
    out = {"standard": {"mode": "STANDARD", "display_text": std["display_text"]},
           "express_eligible": std["express_eligible"], "express": None}
    if std["express_eligible"]:
        exp = order_turnaround(item_codes, express=True)
        surcharge = meta().get("express_surcharge_aed")
        out["express"] = {
            "mode": "EXPRESS", "display_text": exp["display_text"],
            "hours": express_hours(),
            "surcharge_aed": surcharge,   # null until the business configures it
        }
    return out
