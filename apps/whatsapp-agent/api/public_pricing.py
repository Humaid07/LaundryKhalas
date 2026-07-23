"""Public read-only pricing API (task §§12,22,23). UNAUTHENTICATED — the website
and any customer channel read the same PUBLISHED catalogue here. Returns only
approved, customer-facing fields (never internal notes, cost, drafts, audit,
disabled items, or private promos). Version-based ETag caching; fails safe by
falling back to the base catalogue when no version is published yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from db import AsyncSessionLocal, database
from services import catalogue as cat
from services import price_resolver as resolver

router = APIRouter(prefix="/api/public/pricing", tags=["public-pricing"])


def _json_fallback(market: str) -> dict:
    """No published version yet (fresh DB) → serve the seeded base catalogue,
    public projection. Never invents a price; starting/inspection stay flagged."""
    items = []
    for rec in cat.all_items():
        if not rec.get("active", True):
            continue
        items.append({
            "category_code": rec.get("category_code"),
            "category_name": rec.get("category_name"),
            "item_code": rec.get("item_code"),
            "name": rec.get("display_name") or rec.get("name"),
            "description": rec.get("description"),
            "display_price": rec.get("current_price"),
            "regular_price": rec.get("regular_price"),
            "promotion_price": None,
            "pricing_unit": rec.get("pricing_unit"),
            "is_starting_price": rec.get("is_starting_price"),
            "requires_inspection": rec.get("requires_inspection"),
            "promotion_label": None,
            "currency": rec.get("currency", "AED"),
            "vat_note": "Prices exclude 5% VAT." if not cat.prices_include_vat() else "Prices include 5% VAT.",
        })
    items.sort(key=lambda r: (r.get("category_code") or "", r.get("name") or ""))
    return {"catalogue_version": None, "market": market, "items": items, "source": "base"}


async def _published(market: str) -> dict:
    """Current published catalogue (public projection), or the base fallback."""
    if not database.is_supabase_mode():
        # Dev/SQLite: still use the versioned store if a version exists, else base.
        pass
    async with AsyncSessionLocal() as session:
        try:
            data = await resolver.get_published_catalogue(session, market=market, public=True)
        except Exception:  # noqa: BLE001 — table missing / DB down → fail safe
            return _json_fallback(market)
    if data.get("catalogue_version") is None:
        return _json_fallback(market)
    return data


def _etag(data: dict) -> str:
    return f'W/"pricing-{data.get("market","AE")}-v{data.get("catalogue_version") or "base"}"'


@router.get("")
async def public_pricing(request: Request, response: Response, market: str = "AE"):
    data = await _published(market)
    etag = _etag(data)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    return data


@router.get("/version")
async def public_version(market: str = "AE"):
    data = await _published(market)
    return {"catalogue_version": data.get("catalogue_version"), "market": market,
            "source": data.get("source", "published")}


@router.get("/categories")
async def public_categories(market: str = "AE"):
    data = await _published(market)
    seen: dict[str, dict] = {}
    for it in data["items"]:
        code = it.get("category_code")
        if code and code not in seen:
            seen[code] = {"category_code": code, "category_name": it.get("category_name")}
    return {"catalogue_version": data.get("catalogue_version"), "categories": list(seen.values())}


@router.get("/items/{item_code}")
async def public_item(item_code: str, market: str = "AE"):
    data = await _published(market)
    for it in data["items"]:
        if it.get("item_code") == item_code:
            return it
    return Response(status_code=404)
