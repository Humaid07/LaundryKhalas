"""Pricing management — versioned catalogue publishing (task spec §§3-6,15-17).

The single place that mutates the *published* catalogue. Admins edit a DRAFT
version's items without touching live pricing; PUBLISH promotes a draft to the
one `is_current` version atomically (old current → archived); ROLLBACK creates a
NEW published version copying an older one (history is never deleted). Every
material change is written to an immutable audit log.

Backed by SQLAlchemy models (works in SQLite dev/tests AND Supabase) so the whole
lifecycle is deterministically testable. Runtime price reads live in
``services.price_resolver`` (which reads only the current published version + any
active promotion).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    CatalogueVersion, CatalogueVersionItem, PricingAuditLog, PricingPromotion, PricingSyncStatus,
)
from services import catalogue as cat

SUPPORTED_CURRENCIES = frozenset({"AED"})
DRAFT, PENDING_REVIEW, PUBLISHED, ARCHIVED = "draft", "pending_review", "published", "archived"

# Editable, customer-facing / config fields on a version item.
EDITABLE_FIELDS = (
    "display_name", "description", "category_code", "category_name", "service_code",
    "service_name", "current_price", "regular_price", "currency", "pricing_type",
    "pricing_unit", "is_starting_price", "requires_inspection", "requires_measurement",
    "vat_rate", "prices_include_vat", "market", "active", "sort_order", "disclaimer",
    "internal_note",
)

# pricing_unit that each pricing_type REQUIRES (validation §17). Types with a
# None constraint accept any unit label (a fixed/starting/inspection price is the
# same regardless of the unit word, e.g. FIXED_PER_ITEM socks priced per pair).
_TYPE_UNIT = {
    "FIXED_PER_ITEM": None, "STARTING_FROM": None, "PER_PAIR": "PAIR",
    "PER_BAG": "BAG", "PER_KG": "KG", "PER_SQM": "SQM", "PER_SET": "SET",
    "PER_DRESS": "DRESS", "INSPECTION_REQUIRED": None,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns tz-naive datetimes (assumed UTC); Postgres returns aware."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class PricingError(Exception):
    """Validation / workflow error (surfaced as a 400/409 by the API)."""


# --------------------------- version snapshots ------------------------------

def _item_from_catalogue(rec: dict, market: str) -> dict:
    """Map a resolved catalogue record (services.catalogue) to a version-item dict."""
    return {
        "item_code": rec["item_code"],
        "category_code": rec.get("category_code"),
        "category_name": rec.get("category_name"),
        "service_code": rec.get("service_code"),
        "service_name": rec.get("service_name"),
        "canonical_name": rec.get("canonical_name") or rec.get("name") or rec["item_code"],
        "display_name": rec.get("display_name"),
        "description": rec.get("description"),
        "pricing_type": rec.get("pricing_type", "FIXED_PER_ITEM"),
        "pricing_unit": rec.get("pricing_unit", "ITEM"),
        "current_price": rec.get("current_price"),
        "regular_price": rec.get("regular_price"),
        "currency": rec.get("currency", "AED"),
        "is_starting_price": bool(rec.get("is_starting_price")),
        "requires_inspection": bool(rec.get("requires_inspection")),
        "requires_measurement": bool(rec.get("requires_measurement")),
        "vat_rate": cat.vat_rate(),
        "prices_include_vat": cat.prices_include_vat(),
        "market": market,
        "active": bool(rec.get("active", True)),
        "sort_order": rec.get("sort_order", 0),
        "disclaimer": cat.pricing_disclaimer(),
        "internal_note": None,
    }


async def _next_version_number(session: AsyncSession, market: str) -> int:
    rows = (await session.execute(
        select(CatalogueVersion.version_number).where(CatalogueVersion.market == market)
    )).scalars().all()
    return (max(rows) + 1) if rows else 1


async def get_current_published(session: AsyncSession, market: str = "AE") -> CatalogueVersion | None:
    return (await session.execute(
        select(CatalogueVersion).where(
            CatalogueVersion.market == market,
            CatalogueVersion.status == PUBLISHED,
            CatalogueVersion.is_current.is_(True),
        )
    )).scalars().first()


async def ensure_initial_version(session: AsyncSession, market: str = "AE") -> CatalogueVersion:
    """Guarantee a published v1 exists (snapshot of the seeded catalogue). Idempotent."""
    current = await get_current_published(session, market)
    if current:
        return current
    version = CatalogueVersion(
        version_number=await _next_version_number(session, market), status=PUBLISHED,
        is_current=True, market=market, source="seed", created_by="system",
        published_by="system", published_at=_now(), effective_at=_now(),
        change_summary="Initial catalogue snapshot from the approved price list.",
    )
    session.add(version)
    await session.flush()
    for rec in cat.all_items():
        session.add(CatalogueVersionItem(version_id=version.id, **_item_from_catalogue(rec, market)))
    session.add(PricingAuditLog(action="publish", entity_type="version",
                                entity_ref=str(version.version_number), actor="system",
                                version_id=version.id, new_value="v1 seeded"))
    await session.flush()
    return version


async def _items_of(session: AsyncSession, version_id: str) -> list[CatalogueVersionItem]:
    return list((await session.execute(
        select(CatalogueVersionItem).where(CatalogueVersionItem.version_id == version_id)
    )).scalars().all())


# --------------------------- draft lifecycle --------------------------------

async def create_draft(session: AsyncSession, *, actor: str, market: str = "AE",
                       change_summary: str | None = None, source: str = "admin_edit") -> CatalogueVersion:
    """Create a DRAFT version copying the current published items (never live-edits)."""
    base = await ensure_initial_version(session, market)
    draft = CatalogueVersion(
        version_number=await _next_version_number(session, market), status=DRAFT,
        is_current=False, market=market, source=source, created_by=actor,
        change_summary=change_summary,
    )
    session.add(draft)
    await session.flush()
    for it in await _items_of(session, base.id):
        session.add(CatalogueVersionItem(version_id=draft.id, **{
            f: getattr(it, f) for f in (
                "item_code", "category_code", "category_name", "service_code", "service_name",
                "canonical_name", "display_name", "description", "pricing_type", "pricing_unit",
                "current_price", "regular_price", "currency", "is_starting_price",
                "requires_inspection", "requires_measurement", "vat_rate", "prices_include_vat",
                "market", "active", "sort_order", "disclaimer", "internal_note",
            )
        }))
    session.add(PricingAuditLog(action="create", entity_type="version",
                                entity_ref=str(draft.version_number), actor=actor,
                                version_id=draft.id, new_value=f"draft from v{base.version_number}"))
    await session.flush()
    return draft


async def get_version(session: AsyncSession, version_id: str) -> CatalogueVersion | None:
    return await session.get(CatalogueVersion, version_id)


async def update_draft_item(session: AsyncSession, *, version_id: str, item_code: str,
                            changes: dict[str, Any], actor: str,
                            expected_updated: str | None = None) -> CatalogueVersionItem:
    """Apply field changes to ONE item of a DRAFT version, auditing each change.
    Publishing a non-draft is refused. Optimistic-lock via ``expected_updated``
    (the version's updated_at the client last saw)."""
    version = await get_version(session, version_id)
    if not version:
        raise PricingError("Version not found.")
    if version.status != DRAFT:
        raise PricingError("Only draft versions can be edited.")
    if expected_updated is not None and str(version.updated_at) != expected_updated:
        raise PricingError("This draft changed since you opened it — reload and retry.")

    item = (await session.execute(
        select(CatalogueVersionItem).where(
            CatalogueVersionItem.version_id == version_id,
            CatalogueVersionItem.item_code == item_code,
        )
    )).scalars().first()
    if not item:
        raise PricingError(f"Item {item_code} not in this version.")

    for field, new in changes.items():
        if field not in EDITABLE_FIELDS:
            continue
        old = getattr(item, field)
        if old == new:
            continue
        setattr(item, field, new)
        session.add(PricingAuditLog(action="edit", entity_type="item", entity_ref=item_code,
                                    field=field, old_value=str(old), new_value=str(new),
                                    actor=actor, version_id=version_id))
    version.updated_at = _now()
    await session.flush()
    return item


# ------------------------------ validation ----------------------------------

def validate_item(it: CatalogueVersionItem) -> list[str]:
    """Publish-time validation (task §17). Returns a list of error strings."""
    errs: list[str] = []
    if not (it.canonical_name and it.canonical_name.strip()):
        errs.append(f"{it.item_code}: customer-facing name is required.")
    if it.currency not in SUPPORTED_CURRENCIES:
        errs.append(f"{it.item_code}: unsupported currency {it.currency}.")
    if it.current_price is not None and float(it.current_price) < 0:
        errs.append(f"{it.item_code}: price must be non-negative.")
    if it.regular_price is not None and float(it.regular_price) < 0:
        errs.append(f"{it.item_code}: regular price must be non-negative.")
    expected_unit = _TYPE_UNIT.get(it.pricing_type, "no-such-type") if it.pricing_type in _TYPE_UNIT else None
    if it.pricing_type not in _TYPE_UNIT:
        errs.append(f"{it.item_code}: unknown pricing type {it.pricing_type}.")
    elif expected_unit and it.pricing_unit != expected_unit:
        errs.append(f"{it.item_code}: {it.pricing_type} expects unit {expected_unit}, got {it.pricing_unit}.")
    # Starting/inspection items must not carry a guaranteed exact price contract.
    if it.is_starting_price and not (it.pricing_type == "STARTING_FROM" or it.requires_inspection):
        errs.append(f"{it.item_code}: 'from' price must be STARTING_FROM or inspection-required.")
    if it.requires_inspection and it.current_price is None and not it.is_starting_price:
        pass  # inspection with no price is fine (priced after inspection)
    if it.vat_rate is None or float(it.vat_rate) < 0 or float(it.vat_rate) > 1:
        errs.append(f"{it.item_code}: VAT rate must be between 0 and 1.")
    # Active priced items (not starting/inspection) need a price.
    if it.active and it.current_price is None and not (it.is_starting_price or it.requires_inspection):
        errs.append(f"{it.item_code}: active priced item needs a current price.")
    return errs


async def validate_version(session: AsyncSession, version_id: str) -> list[str]:
    items = await _items_of(session, version_id)
    errs: list[str] = []
    seen: set[str] = set()
    for it in items:
        if it.item_code in seen:
            errs.append(f"Duplicate item code {it.item_code}.")
        seen.add(it.item_code)
        errs.extend(validate_item(it))
    return errs


def diff_versions(base_items: list[CatalogueVersionItem],
                  draft_items: list[CatalogueVersionItem]) -> list[dict]:
    """Field-level diff of two item sets (for preview / large-change warnings)."""
    base = {i.item_code: i for i in base_items}
    out: list[dict] = []
    for d in draft_items:
        b = base.get(d.item_code)
        if not b:
            out.append({"item_code": d.item_code, "change": "added", "name": d.canonical_name})
            continue
        changed = {f: (getattr(b, f), getattr(d, f)) for f in EDITABLE_FIELDS
                   if getattr(b, f) != getattr(d, f)}
        if changed:
            out.append({"item_code": d.item_code, "name": d.canonical_name, "change": "modified",
                        "fields": {k: {"old": _s(v[0]), "new": _s(v[1])} for k, v in changed.items()}})
    for code, b in base.items():
        if code not in {d.item_code for d in draft_items}:
            out.append({"item_code": code, "change": "removed", "name": b.canonical_name})
    return out


def _s(v: Any) -> Any:
    return v if v is None or isinstance(v, (int, float, bool, str)) else str(v)


# ------------------------------ publish -------------------------------------

async def publish_version(session: AsyncSession, *, version_id: str, actor: str,
                          effective_at: datetime | None = None) -> CatalogueVersion:
    """Atomically publish a DRAFT: validate → archive current → mark draft
    published + current. One transaction, so runtime never sees a half update."""
    draft = await get_version(session, version_id)
    if not draft:
        raise PricingError("Version not found.")
    if draft.status not in (DRAFT, PENDING_REVIEW):
        raise PricingError("Only a draft (or pending) version can be published.")
    errs = await validate_version(session, version_id)
    if errs:
        raise PricingError("Validation failed: " + "; ".join(errs[:10]))

    # Scheduled publish: leave as pending with an effective_at for the worker.
    if effective_at and effective_at > _now():
        draft.status = PENDING_REVIEW
        draft.effective_at = effective_at
        session.add(PricingAuditLog(action="schedule", entity_type="version",
                                    entity_ref=str(draft.version_number), actor=actor,
                                    version_id=draft.id, new_value=f"effective {effective_at.isoformat()}"))
        await session.flush()
        return draft

    await _activate_version(session, draft, actor, source_action="publish")
    return draft


async def _activate_version(session: AsyncSession, version: CatalogueVersion, actor: str,
                            *, source_action: str) -> None:
    # Archive the previous current, atomically flip this one to current+published.
    await session.execute(
        update(CatalogueVersion)
        .where(CatalogueVersion.market == version.market,
               CatalogueVersion.is_current.is_(True))
        .values(is_current=False, status=ARCHIVED)
    )
    version.status = PUBLISHED
    version.is_current = True
    version.published_by = actor
    version.published_at = _now()
    if not version.effective_at:
        version.effective_at = _now()
    session.add(PricingAuditLog(action=source_action, entity_type="version",
                                entity_ref=str(version.version_number), actor=actor,
                                version_id=version.id, new_value="published"))
    # Record a pending website sync (recovered by the sync worker / API consumer).
    session.add(PricingSyncStatus(target="website", version_id=version.id,
                                  version_number=version.version_number, status="pending",
                                  detail="Awaiting public API consumption / revalidation."))
    session.add(PricingSyncStatus(target="whatsapp_cache", version_id=version.id,
                                  version_number=version.version_number, status="success",
                                  detail="Runtime reads the current published version by version key."))
    await session.flush()


async def rollback_to(session: AsyncSession, *, target_version_number: int, actor: str,
                      market: str = "AE", reason: str | None = None) -> CatalogueVersion:
    """Roll back by creating a NEW published version copying the target's items.
    The replaced version is archived, never deleted (task §16)."""
    target = (await session.execute(
        select(CatalogueVersion).where(CatalogueVersion.market == market,
                                       CatalogueVersion.version_number == target_version_number)
    )).scalars().first()
    if not target:
        raise PricingError(f"Version {target_version_number} not found.")
    new = CatalogueVersion(
        version_number=await _next_version_number(session, market), status=DRAFT,
        is_current=False, market=market, source="rollback",
        rollback_of_version=target_version_number, created_by=actor,
        change_summary=f"Rollback to v{target_version_number}." + (f" {reason}" if reason else ""),
    )
    session.add(new)
    await session.flush()
    for it in await _items_of(session, target.id):
        session.add(CatalogueVersionItem(version_id=new.id, **{
            f: getattr(it, f) for f in (
                "item_code", "category_code", "category_name", "service_code", "service_name",
                "canonical_name", "display_name", "description", "pricing_type", "pricing_unit",
                "current_price", "regular_price", "currency", "is_starting_price",
                "requires_inspection", "requires_measurement", "vat_rate", "prices_include_vat",
                "market", "active", "sort_order", "disclaimer", "internal_note",
            )
        }))
    await _activate_version(session, new, actor, source_action="rollback")
    return new


async def list_versions(session: AsyncSession, market: str = "AE", limit: int = 50) -> list[CatalogueVersion]:
    return list((await session.execute(
        select(CatalogueVersion).where(CatalogueVersion.market == market)
        .order_by(CatalogueVersion.version_number.desc()).limit(limit)
    )).scalars().all())


async def version_items(session: AsyncSession, version_id: str) -> list[CatalogueVersionItem]:
    return await _items_of(session, version_id)


# ------------------------- scheduled activation -----------------------------

async def apply_scheduled(session: AsyncSession, *, market: str = "AE",
                          now: datetime | None = None) -> dict:
    """Idempotently activate due scheduled publishes and expire promotions whose
    window has closed. Safe to run repeatedly (a cron/beat hook in production);
    re-running does nothing once everything due is applied. Promotions also expire
    at *read* time via the resolver window — this just makes the state explicit."""
    now = _aware(now) or _now()
    activated: list[int] = []
    pendings = (await session.execute(
        select(CatalogueVersion).where(
            CatalogueVersion.market == market,
            CatalogueVersion.status == PENDING_REVIEW,
        )
    )).scalars().all()
    for v in pendings:
        eff = _aware(v.effective_at)
        if eff and eff <= now:
            await _activate_version(session, v, actor="scheduler", source_action="publish")
            activated.append(v.version_number)

    expired: list[str] = []
    promos = (await session.execute(
        select(PricingPromotion).where(PricingPromotion.active.is_(True))
    )).scalars().all()
    for p in promos:
        ends = _aware(p.ends_at)
        if ends and ends < now:
            p.active = False
            expired.append(p.id)
            session.add(PricingAuditLog(action="promo_end", entity_type="promotion",
                                        entity_ref=p.item_code, actor="scheduler",
                                        old_value="active", new_value="expired"))
    await session.flush()
    return {"activated_versions": activated, "expired_promotions": expired}
