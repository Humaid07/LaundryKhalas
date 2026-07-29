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
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services import catalogue, money

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


# --------------------------------------------------------------------------
# Express surcharge + same-day cut-off (founder-approved spec §2.4)
# --------------------------------------------------------------------------
def express_surcharge_pct() -> Decimal:
    """Express/same-day surcharge as a fraction of the order total (default 0.5 =
    +50%). Config-driven — never invented in the prompt."""
    return money.to_decimal(meta().get("express_surcharge_pct", 0.5))


def express_cutoff_local() -> str:
    """Local same-day cut-off time, 'HH:MM' (default 15:00 / 3 PM)."""
    return str(meta().get("express_cutoff_local", "15:00"))


def _cutoff_time() -> _dt.time:
    raw = express_cutoff_local()
    try:
        hh, mm = (int(x) for x in raw.split(":", 1))
        return _dt.time(hour=hh, minute=mm)
    except (ValueError, TypeError):
        return _dt.time(hour=15, minute=0)


def is_after_express_cutoff(now_local: _dt.datetime | _dt.time) -> bool:
    """True when a same-day Express request arrives AFTER the local cut-off. Such a
    request is NOT auto-rejected (spec §2.4): the caller checks facility capacity
    and, if unavailable, offers the standard 24h window."""
    t = now_local.time() if isinstance(now_local, _dt.datetime) else now_local
    return t > _cutoff_time()


def apply_express_surcharge(order_total) -> Decimal:
    """The +50% Express order total: round(order_total × (1 + surcharge_pct))."""
    total = money.to_decimal(order_total)
    return money.round_money(total * (Decimal(1) + express_surcharge_pct()))


@dataclass(frozen=True)
class ExpressQuote:
    eligible: bool
    after_cutoff: bool
    requires_facility_check: bool   # True when past cut-off → confirm capacity first
    surcharge_pct: Decimal
    base_total: Decimal
    surcharge_amount: Decimal
    express_total: Decimal

    def to_snapshot(self) -> dict:
        return {
            "express_eligible": self.eligible,
            "after_cutoff": self.after_cutoff,
            "requires_facility_check": self.requires_facility_check,
            "surcharge_pct": float(self.surcharge_pct),
            "base_total": float(self.base_total),
            "surcharge_amount": float(self.surcharge_amount),
            "express_total": float(self.express_total),
        }


def express_quote(item_codes: list[str], order_total,
                  now_local: _dt.datetime | None = None) -> ExpressQuote:
    """Full Express pricing decision for an order: eligibility (every item eligible),
    whether the same-day cut-off has passed (→ facility capacity must be confirmed
    before promising), and the +50% surcharged total. Pure — the caller decides
    whether to actually offer Express based on real facility capacity."""
    base = money.round_money(order_total)
    eligible = order_turnaround(item_codes)["express_eligible"]
    after_cutoff = is_after_express_cutoff(now_local) if now_local is not None else False
    express_total = apply_express_surcharge(base)
    return ExpressQuote(
        eligible=eligible,
        after_cutoff=after_cutoff,
        requires_facility_check=eligible and after_cutoff,
        surcharge_pct=express_surcharge_pct(),
        base_total=base,
        surcharge_amount=money.round_money(express_total - base),
        express_total=express_total,
    )


def delivery_options(item_codes: list[str]) -> dict:
    """Standard + (when eligible) Express options for the delivery-mode step."""
    std = order_turnaround(item_codes, express=False)
    out = {"standard": {"mode": "STANDARD", "display_text": std["display_text"]},
           "express_eligible": std["express_eligible"], "express": None}
    if std["express_eligible"]:
        exp = order_turnaround(item_codes, express=True)
        out["express"] = {
            "mode": "EXPRESS", "display_text": exp["display_text"],
            "hours": express_hours(),
            "surcharge_pct": float(express_surcharge_pct()),   # +50% (spec §2.4)
            "surcharge_aed": meta().get("express_surcharge_aed"),  # legacy fixed fee, unused
            "cutoff_local": express_cutoff_local(),
        }
    return out
