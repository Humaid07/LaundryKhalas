"""Item-level service catalogue accessor + alias resolution.

Single in-process reader for ``config/laundry_catalogue.json`` — the reviewed
structured seed data transcribed from the approved Laundry Khalas price-list
image. The SAME file is imported into PostgreSQL/Supabase by
``scripts/seed_service_catalogue.py`` (the DB is the runtime source of truth for
the catalogue APIs and dashboard); this loader keeps the agent and the pricing
engine reading the identical, cached data with no DB round-trip on the hot path.
An idempotent seed + a health check keep the JSON and the DB in lockstep (the
same pattern the service-taxonomy sync already established).

Design contract (CLAUDE.md §5-9, task spec §§1-8/12):
  * Prices are the BOLD current price from the image (``current_price``); a
    crossed-out value is stored separately as ``regular_price`` and is NEVER the
    selling price.
  * ``is_starting_price``/``requires_inspection`` items ('From …') must never be
    turned into a guaranteed total — the pricing engine enforces this.
  * Identity is the stable ``code`` (never the display label). Interactive-list
    rowIds use these codes.
This module is a leaf (imports nothing from the agent) so anything may import it.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_CATALOGUE_FILE = "laundry_catalogue.json"

# Pricing types (task spec §3). The effective type of an item is its own
# ``pricing_type``, else its category's ``default_pricing_type``, else FIXED.
FIXED_PER_ITEM = "FIXED_PER_ITEM"
STARTING_FROM = "STARTING_FROM"
PER_PAIR = "PER_PAIR"
PER_BAG = "PER_BAG"
PER_KG = "PER_KG"
PER_SQM = "PER_SQM"
INSPECTION_REQUIRED = "INSPECTION_REQUIRED"

# Types that produce an EXACT price when a quantity is known.
_EXACT_TYPES = frozenset({FIXED_PER_ITEM, PER_PAIR, PER_BAG})
# Types that need a measurement/weight before even an estimate is firm.
_MEASURED_TYPES = frozenset({PER_SQM, PER_KG})


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads((_CONFIG_DIR / _CATALOGUE_FILE).read_text(encoding="utf-8"))


def reload_catalogue() -> None:
    """Drop the cache (used by tests / after a seed edit). Defensive so it is
    safe to call even while a test has monkeypatched ``_raw``/``_index``."""
    for fn in (_raw, _index):
        clear = getattr(fn, "cache_clear", None)
        if clear:
            clear()


def meta() -> dict:
    return _raw()["meta"]


def vat_rate() -> float:
    return float(meta().get("vat_rate", 0.05))


def currency() -> str:
    return meta().get("currency", "AED")


def prices_include_vat() -> bool:
    return bool(meta().get("prices_include_vat", False))


def pricing_disclaimer() -> str:
    return meta().get("business", {}).get(
        "pricing_disclaimer",
        "Prices may vary depending on item condition, material and brand.",
    )


def business_info() -> dict:
    return meta().get("business", {})


def categories() -> list[dict]:
    """Ordered active categories (the WhatsApp step-1 list)."""
    cats = [c for c in _raw()["categories"] if c.get("active", True)]
    return sorted(cats, key=lambda c: c.get("sort_order", 0))


def category_by_code(code: str | None) -> dict | None:
    if not code:
        return None
    for c in _raw()["categories"]:
        if c.get("code") == code:
            return c
    return None


def services_for_category(category_code: str) -> list[dict]:
    """Ordered sub-category services within a category (the WhatsApp step-2 list
    when a category has more than one sub-group)."""
    cat = category_by_code(category_code)
    if not cat:
        return []
    svcs = [s for s in cat.get("services", []) if s.get("active", True)]
    return sorted(svcs, key=lambda s: s.get("sort_order", 0))


def _effective_type(item: dict, service: dict, category: dict) -> str:
    return (
        item.get("pricing_type")
        or category.get("default_pricing_type")
        or FIXED_PER_ITEM
    )


def _effective_unit(item: dict, service: dict, category: dict) -> str:
    return (
        item.get("pricing_unit")
        or category.get("default_pricing_unit")
        or "ITEM"
    )


def _normalise_item(item: dict, service: dict, category: dict) -> dict:
    """Flatten an item into a fully-resolved catalogue record (task spec §3
    field list). Defaults inherited from service/category are made explicit so
    every downstream consumer (agent, pricing, API, snapshot) sees one shape."""
    ptype = _effective_type(item, service, category)
    is_starting = bool(item.get("is_starting_price", ptype == STARTING_FROM))
    requires_inspection = bool(
        item.get("requires_inspection", ptype in (STARTING_FROM, INSPECTION_REQUIRED))
    )
    requires_measurement = bool(
        item.get("requires_measurement", ptype in (PER_SQM,))
    )
    return {
        "item_code": item["code"],
        "code": item["code"],
        "category_code": category["code"],
        "category_name": category["name"],
        "service_code": service["code"],
        "service_name": service["name"],
        "canonical_name": item["name"],
        "display_name": item.get("display_name", item["name"]),
        "name": item["name"],
        "description": item.get("description"),
        "pricing_type": ptype,
        "pricing_unit": _effective_unit(item, service, category),
        "current_price": _num(item.get("current_price")),
        "regular_price": _num(item.get("regular_price")),
        "currency": currency(),
        "is_starting_price": is_starting,
        "requires_inspection": requires_inspection,
        "requires_measurement": requires_measurement,
        "bag_limit_kg": item.get("bag_limit_kg"),
        "note": item.get("note"),
        "aliases": [a.lower() for a in item.get("aliases", [])],
        "active": bool(item.get("active", True)),
        "sort_order": item.get("sort_order", 0),
        "source": "Approved Laundry Khalas price-list image",
    }


def _num(v):
    return None if v is None else float(v)


@lru_cache(maxsize=1)
def _index() -> dict:
    """Build lookup indexes once: by item code, and an alias->codes map.

    Aliases are matched by the pricing/agent resolver; a longer alias is
    preferred on overlap so "designer sneakers" beats "sneakers"."""
    by_code: dict[str, dict] = {}
    alias_map: dict[str, set[str]] = {}
    all_items: list[dict] = []
    for category in categories():
        for service in services_for_category(category["code"]):
            for raw_item in service.get("items", []):
                if not raw_item.get("active", True):
                    continue
                rec = _normalise_item(raw_item, service, category)
                by_code[rec["item_code"]] = rec
                all_items.append(rec)
                for alias in rec["aliases"] + [rec["canonical_name"].lower()]:
                    alias_map.setdefault(alias, set()).add(rec["item_code"])
    return {"by_code": by_code, "alias_map": alias_map, "all_items": all_items}


def all_items() -> list[dict]:
    return list(_index()["all_items"])


def item_by_code(code: str | None) -> dict | None:
    if not code:
        return None
    return _index()["by_code"].get(code)


def items_for_category(category_code: str) -> list[dict]:
    return [i for i in all_items() if i["category_code"] == category_code]


def items_for_service(service_code: str) -> list[dict]:
    return [i for i in all_items() if i["service_code"] == service_code]


def resolve_category_alias(text: str) -> str | None:
    """Return a category code if the free text clearly names ONE category, else
    None. Used only to pre-select a category — item selection is a separate step."""
    if not text:
        return None
    low = text.lower()
    matched: set[str] = set()
    for c in categories():
        names = [c["name"].lower()] + [a.lower() for a in c.get("aliases", [])]
        if any(a and a in low for a in names):
            matched.add(c["code"])
    return matched.pop() if len(matched) == 1 else None


def resolve_item_alias(text: str, *, category_code: str | None = None) -> tuple[list[str], str]:
    """Resolve free text to catalogue item code(s).

    Returns ``(codes, reason)`` where reason is 'ok' (unique), 'ambiguous'
    (>1 candidate — the agent must ask), or 'none'. When ``category_code`` is
    given, matching is scoped to that category so "shirt" under Press Only maps
    to the on-hanger item rather than the Clean & Press one (task spec §7)."""
    if not text:
        return [], "none"
    low = f" {text.lower()} "
    alias_map = _index()["alias_map"]
    scope = None
    if category_code:
        scope = {i["item_code"] for i in items_for_category(category_code)}

    # Prefer the longest alias that appears as a whole word/phrase.
    hits: dict[str, int] = {}  # item_code -> longest matched alias length
    for alias, codes in alias_map.items():
        if not alias:
            continue
        if f" {alias} " in low or low.strip() == alias:
            for code in codes:
                if scope is not None and code not in scope:
                    continue
                hits[code] = max(hits.get(code, 0), len(alias))
    if not hits:
        return [], "none"
    best = max(hits.values())
    winners = [c for c, ln in hits.items() if ln == best]
    if len(winners) == 1:
        return winners, "ok"
    return sorted(winners), "ambiguous"


# Bare "iron"/"ironing"/"press" is genuinely ambiguous between Clean & Press
# (wash AND iron) and Press Only (iron a pre-washed item). The agent must ask
# rather than guess (task spec §7/§20). A qualifier resolves it.
_PRESS_ONLY_QUALIFIERS = (
    "press only", "pressing only", "iron only", "ironing only", "just iron",
    "just press", "only iron", "only press", "already washed",
)
_CLEAN_PRESS_QUALIFIERS = (
    "wash and iron", "wash & iron", "clean and press", "clean & press",
    "dry clean", "dry-clean", "wash and press",
)


def is_ambiguous_iron(text: str | None) -> bool:
    """True when the text asks for ironing/pressing without saying whether the
    item still needs washing (Clean & Press) or is already washed (Press Only)."""
    if not text:
        return False
    low = text.lower()
    if not any(w in low for w in ("iron", "press")):
        return False
    if any(q in low for q in _PRESS_ONLY_QUALIFIERS):
        return False
    if any(q in low for q in _CLEAN_PRESS_QUALIFIERS):
        return False
    return True


def category_options() -> list[dict]:
    """[{id, code, title, description}] for the WhatsApp step-1 category list."""
    return [
        {"id": f"cat:{c['code']}", "code": c["code"], "title": c["name"],
         "description": c.get("description")}
        for c in categories()
    ]


def item_price_label(item: dict) -> str:
    """Short price string for an interactive list row / quote line, e.g.
    'AED 9 per item', 'From AED 50 per pair', 'AED 20 per sqm'."""
    unit = (item.get("pricing_unit") or "ITEM").lower()
    unit_word = {"item": "item", "pair": "pair", "bag": "bag", "kg": "kg",
                 "sqm": "sqm"}.get(unit, unit)
    price = item.get("current_price")
    if price is None:
        return "Priced after inspection"
    money = _fmt_money(price)
    prefix = "From " if item.get("is_starting_price") else ""
    return f"{prefix}AED {money} per {unit_word}"


def _fmt_money(v: float) -> str:
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.2f}"
