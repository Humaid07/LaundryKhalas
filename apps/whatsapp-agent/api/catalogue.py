"""Item-level catalogue + pricing API (task spec §12).

Serves the approved Laundry Khalas catalogue from the DB (runtime source of
truth; falls back to the cached JSON seed when the DB is not seeded) and the
VAT-aware quote calculator. The LLM never holds the full catalogue — it may
identify intent + candidate items, but the backend validates the item and
returns the price. Read/compute only; no live external calls.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from db.repositories import catalogue_repo
from services import catalogue as cat
from services import pricing

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])


@router.get("")
async def get_catalogue():
    """Catalogue metadata (currency, VAT, source, verification date, business info)."""
    return {"meta": cat.meta(), "categories": await catalogue_repo.list_categories()}


@router.get("/categories")
async def list_categories():
    """list_service_categories() — the WhatsApp step-1 category list."""
    return {"categories": await catalogue_repo.list_categories()}


@router.get("/items")
async def list_items(category: str | None = None):
    """list_service_items(category_id) — items, optionally scoped to a category."""
    return {"items": await catalogue_repo.list_items(category)}


@router.get("/items/{item_code}")
async def get_item(item_code: str):
    """get_service_price(item_id) — the full priced catalogue record, or 404-shape null."""
    item = await catalogue_repo.get_item(item_code)
    return {"item": item}


class ResolveRequest(BaseModel):
    text: str
    category_code: str | None = None


@router.post("/resolve")
async def resolve_alias(req: ResolveRequest):
    """resolve_service_alias(customer_text) — map free text to catalogue candidates.

    Returns a category suggestion, item candidate(s) + a reason ('ok' unique,
    'ambiguous', 'none'), and whether the text is an ambiguous iron/press request
    the agent must disambiguate."""
    codes, reason = cat.resolve_item_alias(req.text, category_code=req.category_code)
    return {
        "category": cat.resolve_category_alias(req.text),
        "items": codes,
        "reason": reason,
        "ambiguous_iron": cat.is_ambiguous_iron(req.text),
    }


class QuoteItem(BaseModel):
    item_code: str
    quantity: float = 1
    measure: float | None = None


class QuoteRequest(BaseModel):
    items: list[QuoteItem]


@router.post("/quote")
async def calculate_quote(req: QuoteRequest):
    """calculate_order_estimate(order_items) — a VAT-aware quote. Starting/
    inspection ('From') lines are itemised but excluded from the payable total
    (never presented as a guaranteed amount)."""
    quote = pricing.calculate_estimate([i.model_dump() for i in req.items])
    return {"quote": quote.to_dict(), "summary": pricing.format_quote_summary(quote)}


@router.get("/health")
async def catalogue_health():
    """DB↔JSON parity for the catalogue (drives a dashboard drift warning)."""
    return await catalogue_repo.sync_status()
