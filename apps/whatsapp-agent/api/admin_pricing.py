"""Admin pricing-management API (task §22). Admin-only per-permission guards;
every write is audited; publishing is atomic and validated. Draft pricing is
never exposed to customers — that's the separate public router.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from db import AsyncSessionLocal
from models import CatalogueVersion, PricingAuditLog, PricingPromotion, PricingSyncStatus
from services import pricing_management as pm
from services import price_resolver as resolver
from services import pricing_permissions as perms

router = APIRouter(prefix="/api/admin/pricing", tags=["admin-pricing"])


# ------------------------------ request models ------------------------------
class DraftCreate(BaseModel):
    change_summary: str | None = None
    market: str = "AE"


class ItemPatch(BaseModel):
    changes: dict
    expected_updated: str | None = None  # optimistic lock


class PublishReq(BaseModel):
    effective_at: datetime | None = None


class RollbackReq(BaseModel):
    reason: str | None = None
    market: str = "AE"


class PromoCreate(BaseModel):
    item_code: str
    name: str
    promo_price: float
    description: str | None = None
    market: str = "AE"
    priority: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ImportReq(BaseModel):
    items: list[dict]  # [{item_code, ...editable fields}]
    change_summary: str | None = None
    market: str = "AE"


def _version_dict(v: CatalogueVersion) -> dict:
    return {
        "id": v.id, "version_number": v.version_number, "status": v.status,
        "is_current": v.is_current, "market": v.market, "change_summary": v.change_summary,
        "source": v.source, "rollback_of_version": v.rollback_of_version,
        "created_by": v.created_by, "published_by": v.published_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "effective_at": v.effective_at.isoformat() if v.effective_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


def _item_dict(it) -> dict:
    d = {c: getattr(it, c) for c in (
        "id", "item_code", "category_code", "category_name", "service_code", "service_name",
        "canonical_name", "display_name", "description", "pricing_type", "pricing_unit",
        "current_price", "regular_price", "currency", "is_starting_price", "requires_inspection",
        "requires_measurement", "vat_rate", "prices_include_vat", "market", "active",
        "sort_order", "disclaimer", "internal_note",
    )}
    return d


# --------------------------------- versions ---------------------------------
@router.get("/versions")
async def list_versions(request: Request, market: str = "AE",
                        user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        await pm.ensure_initial_version(session, market)
        await session.commit()
        vs = await pm.list_versions(session, market)
        return {"versions": [_version_dict(v) for v in vs]}


@router.get("/versions/{version_id}")
async def get_version(version_id: str, request: Request,
                      user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        v = await pm.get_version(session, version_id)
        if not v:
            raise HTTPException(404, "Version not found.")
        items = await pm.version_items(session, version_id)
        current = await pm.get_current_published(session, v.market)
        diff = []
        if current and current.id != version_id:
            diff = pm.diff_versions(await pm.version_items(session, current.id), items)
        return {"version": _version_dict(v), "items": [_item_dict(i) for i in items], "diff": diff}


@router.post("/versions", status_code=201)
async def create_draft(body: DraftCreate, request: Request,
                       user: dict = Depends(perms.require_pricing(perms.CREATE))):
    async with AsyncSessionLocal() as session:
        draft = await pm.create_draft(session, actor=user.get("email", "admin"),
                                      market=body.market, change_summary=body.change_summary)
        await session.commit()
        return _version_dict(draft)


@router.patch("/versions/{version_id}/items/{item_code}")
async def patch_item(version_id: str, item_code: str, body: ItemPatch, request: Request,
                     user: dict = Depends(perms.require_pricing(perms.EDIT))):
    async with AsyncSessionLocal() as session:
        try:
            item = await pm.update_draft_item(
                session, version_id=version_id, item_code=item_code, changes=body.changes,
                actor=user.get("email", "admin"), expected_updated=body.expected_updated)
        except pm.PricingError as e:
            raise HTTPException(409, str(e))
        await session.commit()
        return _item_dict(item)


@router.post("/versions/{version_id}/publish")
async def publish(version_id: str, body: PublishReq, request: Request,
                  user: dict = Depends(perms.require_pricing(perms.PUBLISH))):
    async with AsyncSessionLocal() as session:
        try:
            v = await pm.publish_version(session, version_id=version_id,
                                         actor=user.get("email", "admin"),
                                         effective_at=body.effective_at)
        except pm.PricingError as e:
            raise HTTPException(400, str(e))
        await session.commit()
        resolver.invalidate(v.market)
        return _version_dict(v)


@router.post("/versions/{version_number}/rollback")
async def rollback(version_number: int, body: RollbackReq, request: Request,
                   user: dict = Depends(perms.require_pricing(perms.ROLLBACK))):
    async with AsyncSessionLocal() as session:
        try:
            v = await pm.rollback_to(session, target_version_number=version_number,
                                     actor=user.get("email", "admin"), market=body.market,
                                     reason=body.reason)
        except pm.PricingError as e:
            raise HTTPException(400, str(e))
        await session.commit()
        resolver.invalidate(v.market)
        return _version_dict(v)


# ------------------------------ items / current -----------------------------
@router.get("/items")
async def current_items(request: Request, market: str = "AE",
                        user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        await pm.ensure_initial_version(session, market)
        await session.commit()
        cat = await resolver.get_published_catalogue(session, market=market, public=False)
        return cat


# ------------------------------ promotions ----------------------------------
@router.get("/promotions")
async def list_promotions(request: Request, market: str = "AE",
                          user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(PricingPromotion).where(PricingPromotion.market == market)
            .order_by(PricingPromotion.created_at.desc())
        )).scalars().all()
        return {"promotions": [{
            "id": p.id, "item_code": p.item_code, "name": p.name, "promo_price": p.promo_price,
            "active": p.active, "priority": p.priority,
            "starts_at": p.starts_at.isoformat() if p.starts_at else None,
            "ends_at": p.ends_at.isoformat() if p.ends_at else None,
        } for p in rows]}


@router.post("/promotions", status_code=201)
async def create_promotion(body: PromoCreate, request: Request,
                           user: dict = Depends(perms.require_pricing(perms.EDIT))):
    async with AsyncSessionLocal() as session:
        p = PricingPromotion(item_code=body.item_code, name=body.name, promo_price=body.promo_price,
                             description=body.description, market=body.market, priority=body.priority,
                             starts_at=body.starts_at, ends_at=body.ends_at,
                             created_by=user.get("email", "admin"))
        session.add(p)
        session.add(PricingAuditLog(action="promo_start", entity_type="promotion",
                                    entity_ref=body.item_code, actor=user.get("email", "admin"),
                                    new_value=f"{body.name} @ {body.promo_price}"))
        await session.commit()
        resolver.invalidate(body.market)
        return {"id": p.id}


@router.post("/promotions/{promo_id}/end")
async def end_promotion(promo_id: str, request: Request,
                        user: dict = Depends(perms.require_pricing(perms.EDIT))):
    async with AsyncSessionLocal() as session:
        p = await session.get(PricingPromotion, promo_id)
        if not p:
            raise HTTPException(404, "Promotion not found.")
        p.active = False
        session.add(PricingAuditLog(action="promo_end", entity_type="promotion", entity_ref=p.item_code,
                                    actor=user.get("email", "admin"), old_value="active", new_value="ended"))
        await session.commit()
        resolver.invalidate(p.market)
        return {"id": p.id, "active": False}


# ------------------------------ history / sync -------------------------------
@router.get("/history")
async def history(request: Request, limit: int = 100,
                  user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(PricingAuditLog).order_by(PricingAuditLog.created_at.desc()).limit(limit)
        )).scalars().all()
        return {"history": [{
            "action": r.action, "entity_type": r.entity_type, "entity_ref": r.entity_ref,
            "field": r.field, "old_value": r.old_value, "new_value": r.new_value,
            "actor": r.actor, "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]}


@router.get("/sync-status")
async def sync_status(request: Request, market: str = "AE",
                      user: dict = Depends(perms.require_pricing(perms.VIEW))):
    async with AsyncSessionLocal() as session:
        current = await pm.get_current_published(session, market)
        rows = (await session.execute(
            select(PricingSyncStatus).order_by(PricingSyncStatus.attempted_at.desc()).limit(20)
        )).scalars().all()
        return {
            "published_version": current.version_number if current else None,
            "published_at": current.published_at.isoformat() if current and current.published_at else None,
            "sync": [{"target": r.target, "version_number": r.version_number, "status": r.status,
                      "detail": r.detail,
                      "attempted_at": r.attempted_at.isoformat() if r.attempted_at else None}
                     for r in rows],
        }


# ------------------------------ import / export -----------------------------
@router.get("/export")
async def export_catalogue(request: Request, market: str = "AE", format: str = "json",
                           user: dict = Depends(perms.require_pricing(perms.EXPORT))):
    async with AsyncSessionLocal() as session:
        await pm.ensure_initial_version(session, market)
        await session.commit()
        cat = await resolver.get_published_catalogue(session, market=market, public=False)
    items = cat["items"]
    if format == "csv":
        buf = io.StringIO()
        cols = ["item_code", "category_code", "canonical_name", "pricing_type", "pricing_unit",
                "current_price", "regular_price", "currency", "is_starting_price",
                "requires_inspection", "active"]
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in items:
            w.writerow(it)
        return Response(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=catalogue.csv"})
    return {"catalogue_version": cat["catalogue_version"], "market": market, "items": items}


@router.post("/import", status_code=201)
async def import_catalogue(body: ImportReq, request: Request,
                           user: dict = Depends(perms.require_pricing(perms.IMPORT))):
    """Validate a price sheet and stage it as a DRAFT (never publishes). Idempotent
    on item_code. Returns the created draft + a change preview."""
    async with AsyncSessionLocal() as session:
        draft = await pm.create_draft(session, actor=user.get("email", "admin"),
                                      market=body.market, source="import",
                                      change_summary=body.change_summary or "Imported price sheet")
        applied, skipped = 0, []
        for row in body.items:
            code = row.get("item_code")
            if not code:
                skipped.append("row missing item_code")
                continue
            changes = {k: v for k, v in row.items() if k in pm.EDITABLE_FIELDS}
            try:
                await pm.update_draft_item(session, version_id=draft.id, item_code=code,
                                           changes=changes, actor=user.get("email", "admin"))
                applied += 1
            except pm.PricingError as e:
                skipped.append(f"{code}: {e}")
        session.add(PricingAuditLog(action="import", entity_type="version",
                                    entity_ref=str(draft.version_number),
                                    actor=user.get("email", "admin"),
                                    new_value=f"{applied} applied, {len(skipped)} skipped"))
        await session.commit()
        return {"draft_version_id": draft.id, "version_number": draft.version_number,
                "applied": applied, "skipped": skipped}


# ------------------------------ my permissions ------------------------------
@router.get("/permissions")
async def my_permissions(request: Request,
                         user: dict = Depends(perms.require_pricing(perms.VIEW))):
    return {"role": user.get("role"), "permissions": sorted(perms.permissions_for(user.get("role")))}
