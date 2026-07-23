"""Runtime price resolution over the PUBLISHED catalogue version (+ promotions).

Every runtime consumer — WhatsApp agent, public website API, dashboard — reads
prices ONLY through here, so they all see exactly one atomic published version.
Draft/pending pricing is never returned. Promotions overlay the published base
with deterministic precedence (task §8):

  1. (customer/contract pricing — not supported yet)
  2. active market promotion (within its window)
  3. published current price
  4. regular price
  5. starting-price / inspection-required fallback (pending — no firm total)

Reads are cached per (market, version_number). Because the cache key includes
the published version number, publishing a new version *is* the invalidation —
the next read misses the old key and repopulates. `invalidate()` clears eagerly.
If the DB is unavailable, callers fall back to the JSON catalogue
(`services.catalogue`) so the agent never invents a price (task §24).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CatalogueVersion, CatalogueVersionItem, PricingPromotion
from services import pricing_management as pm

# (market, version_number) -> {"items": {code: dict}, "version": int}
_CACHE: dict[tuple[str, int], dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Normalise to aware-UTC. SQLite returns tz-naive datetimes (assumed UTC);
    Postgres returns aware ones — so promotion windows compare correctly on both."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def invalidate(market: str | None = None) -> None:
    if market is None:
        _CACHE.clear()
    else:
        for k in [k for k in _CACHE if k[0] == market]:
            _CACHE.pop(k, None)


async def current_version_number(session: AsyncSession, market: str = "AE") -> int | None:
    v = await pm.get_current_published(session, market)
    return v.version_number if v else None


def _item_dict(it: CatalogueVersionItem) -> dict:
    return {
        "item_code": it.item_code, "category_code": it.category_code,
        "category_name": it.category_name, "service_code": it.service_code,
        "service_name": it.service_name, "canonical_name": it.canonical_name,
        "name": it.canonical_name, "display_name": it.display_name or it.canonical_name,
        "description": it.description, "pricing_type": it.pricing_type,
        "pricing_unit": it.pricing_unit, "current_price": it.current_price,
        "regular_price": it.regular_price, "currency": it.currency,
        "is_starting_price": it.is_starting_price, "requires_inspection": it.requires_inspection,
        "requires_measurement": it.requires_measurement, "vat_rate": it.vat_rate,
        "prices_include_vat": it.prices_include_vat, "market": it.market,
        "active": it.active, "sort_order": it.sort_order, "disclaimer": it.disclaimer,
        "internal_note": it.internal_note,
    }


async def _published_items(session: AsyncSession, market: str) -> dict | None:
    """The current published version's active items, cached by version number."""
    version = await pm.get_current_published(session, market)
    if not version:
        return None
    key = (market, version.version_number)
    if key in _CACHE:
        return _CACHE[key]
    items = (await session.execute(
        select(CatalogueVersionItem).where(
            CatalogueVersionItem.version_id == version.id,
            CatalogueVersionItem.active.is_(True),
        )
    )).scalars().all()
    snap = {"version": version.version_number,
            "items": {it.item_code: _item_dict(it) for it in items}}
    _CACHE[key] = snap
    return snap


async def _active_promo(session: AsyncSession, item_code: str, market: str,
                        at: datetime) -> PricingPromotion | None:
    promos = (await session.execute(
        select(PricingPromotion).where(
            PricingPromotion.item_code == item_code,
            PricingPromotion.market == market,
            PricingPromotion.active.is_(True),
        ).order_by(PricingPromotion.priority.desc())
    )).scalars().all()
    at = _aware(at)
    for p in promos:
        starts, ends = _aware(p.starts_at), _aware(p.ends_at)
        if starts and starts > at:
            continue
        if ends and ends < at:
            continue
        return p
    return None


def _resolve(base: dict, promo: PricingPromotion | None) -> dict:
    """Apply precedence to a published item + optional active promo."""
    out = dict(base)
    pending = base["is_starting_price"] or base["requires_inspection"] or base["current_price"] is None
    if promo and not pending:
        out["effective_price"] = float(promo.promo_price)
        out["price_source"] = "promotion"
        out["promotion"] = {"name": promo.name, "was": base["current_price"], "id": promo.id}
    elif base["current_price"] is not None:
        out["effective_price"] = float(base["current_price"])
        out["price_source"] = "published" if not pending else "starting"
    elif base["regular_price"] is not None:
        out["effective_price"] = float(base["regular_price"])
        out["price_source"] = "regular"
    else:
        out["effective_price"] = None
        out["price_source"] = "pending"
    if pending:
        out["price_source"] = "pending" if base["current_price"] is None else "starting"
    return out


async def get_effective_price(session: AsyncSession, item_code: str, *, market: str = "AE",
                              at: datetime | None = None) -> dict | None:
    at = at or _now()
    snap = await _published_items(session, market)
    if not snap or item_code not in snap["items"]:
        return None
    promo = await _active_promo(session, item_code, market, at)
    resolved = _resolve(snap["items"][item_code], promo)
    resolved["catalogue_version"] = snap["version"]
    return resolved


async def get_published_catalogue(session: AsyncSession, *, market: str = "AE",
                                  at: datetime | None = None, public: bool = False) -> dict:
    """The full effective published catalogue (base + active promos). When
    ``public`` is True, internal-only fields are stripped (task §12)."""
    at = at or _now()
    snap = await _published_items(session, market)
    if not snap:
        return {"catalogue_version": None, "market": market, "items": []}
    out = []
    for code, base in snap["items"].items():
        promo = await _active_promo(session, code, market, at)
        rec = _resolve(base, promo)
        out.append(_public_projection(rec) if public else rec)
    out.sort(key=lambda r: (r.get("category_code") or "", r.get("sort_order") or 0, r.get("name") or ""))
    return {"catalogue_version": snap["version"], "market": market, "items": out}


def _public_projection(rec: dict) -> dict:
    """Customer-facing subset only — NO internal notes, ids, cost, audit (task §12)."""
    return {
        "category_code": rec.get("category_code"),
        "category_name": rec.get("category_name"),
        "item_code": rec.get("item_code"),
        "name": rec.get("display_name") or rec.get("name"),
        "description": rec.get("description"),
        "display_price": rec.get("effective_price"),
        "regular_price": rec.get("regular_price"),
        "promotion_price": (rec.get("promotion") or {}).get("was") is not None and rec.get("effective_price") or None,
        "pricing_unit": rec.get("pricing_unit"),
        "is_starting_price": rec.get("is_starting_price"),
        "requires_inspection": rec.get("requires_inspection"),
        "promotion_label": (rec.get("promotion") or {}).get("name"),
        "currency": rec.get("currency"),
        "vat_note": _vat_note(rec),
    }


def _vat_note(rec: dict) -> str:
    return ("Prices include 5% VAT." if rec.get("prices_include_vat")
            else "Prices exclude 5% VAT.")


async def published_overrides(session: AsyncSession, *, market: str = "AE",
                              at: datetime | None = None) -> dict[str, float]:
    """{item_code: effective_price} for items with a FIRM published/promotional
    price, for ``pricing.calculate_estimate(..., price_overrides=...)``. Pending
    'from'/inspection items are omitted so they can never become a firm total.
    Empty when no version is published (agent then uses the base catalogue)."""
    cat = await get_published_catalogue(session, market=market, at=at, public=False)
    out: dict[str, float] = {}
    for rec in cat["items"]:
        if rec.get("price_source") in ("published", "promotion") and rec.get("effective_price") is not None:
            out[rec["item_code"]] = float(rec["effective_price"])
    return out
