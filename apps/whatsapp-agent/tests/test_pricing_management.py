"""Pricing management + dynamic pricing tests (task §25 scenarios).

Service-level (SQLAlchemy store, hermetic in SQLite) + a few HTTP checks for the
public API and permission guards. Each test starts from a clean pricing store.
"""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import delete
from starlette.requests import Request

from db import AsyncSessionLocal, init_db
from models import (
    CatalogueVersion, CatalogueVersionItem, PricingAuditLog, PricingPromotion, PricingSyncStatus, Order,
)
from services import catalogue as cat
from services import price_resolver as resolver
from services import pricing_management as pm
from services import pricing_permissions as perms


@pytest_asyncio.fixture(autouse=True)
async def _reset_pricing():
    await init_db()
    async with AsyncSessionLocal() as s:
        for M in (CatalogueVersionItem, CatalogueVersion, PricingPromotion,
                  PricingAuditLog, PricingSyncStatus):
            await s.execute(delete(M))
        await s.commit()
    resolver.invalidate()
    yield


def _exact_code() -> str:
    for it in cat.all_items():
        if (it.get("current_price") and not it.get("is_starting_price")
                and not it.get("requires_inspection")
                and it.get("pricing_type") in ("FIXED_PER_ITEM", "PER_PAIR", "PER_BAG")):
            return it["item_code"]
    raise RuntimeError("no exact-priced item in catalogue")


def _starting_code() -> str | None:
    for it in cat.all_items():
        if it.get("is_starting_price") or it.get("requires_inspection"):
            return it["item_code"]
    return None


async def _publish_price_change(session, code, new_price, actor="admin@x"):
    draft = await pm.create_draft(session, actor=actor)
    await pm.update_draft_item(session, version_id=draft.id, item_code=code,
                               changes={"current_price": new_price}, actor=actor)
    await pm.publish_version(session, version_id=draft.id, actor=actor)
    await session.commit()
    resolver.invalidate()
    return draft


# 1/7. Initial version + publish activates a version -------------------------
async def test_initial_version_and_publish_activates_new():
    async with AsyncSessionLocal() as s:
        v1 = await pm.ensure_initial_version(s)
        await s.commit()
        assert v1.version_number == 1 and v1.status == "published" and v1.is_current
        code = _exact_code()
        before = await resolver.get_effective_price(s, code)
        await _publish_price_change(s, code, (before["effective_price"] or 0) + 123)
        current = await pm.get_current_published(s)
        assert current.version_number == 2 and current.is_current
        after = await resolver.get_effective_price(s, code)
        assert after["effective_price"] == (before["effective_price"] or 0) + 123
        assert after["catalogue_version"] == 2


# 4/5/6. Draft does not affect runtime until published -----------------------
async def test_draft_does_not_affect_runtime():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        draft = await pm.create_draft(s, actor="a@x")
        await pm.update_draft_item(s, version_id=draft.id, item_code=code,
                                   changes={"current_price": base + 999}, actor="a@x")
        await s.commit()
        resolver.invalidate()
        # Still the published price — the draft is invisible to runtime.
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base
        assert draft.status == "draft" and not draft.is_current


# 8/9. Public API reflects published price, excludes internal -----------------
async def test_public_catalogue_reflects_publish_and_hides_internal(client):
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        await _publish_price_change(s, code, 777.0)
    r = await client.get("/api/public/pricing")
    assert r.status_code == 200
    body = r.json()
    item = next(i for i in body["items"] if i["item_code"] == code)
    assert item["display_price"] == 777.0
    assert "internal_note" not in item and "id" not in item  # §12/§27


# 10. Historical orders keep their snapshot ----------------------------------
async def test_historical_order_snapshot_unchanged():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        # A confirmed order froze its own pricing (JSON snapshot on the row).
        o = Order(order_id="LK-TEST-PRICE", items=[{"name": "Shirt", "qty": 3}],
                  amount=51.45, is_demo=True, status="pickup_scheduled")
        s.add(o)
        await s.commit()
        code = _exact_code()
        await _publish_price_change(s, code, 999.0)
        again = await s.get(Order, o.id)
        assert again.amount == 51.45  # publishing never re-prices a historical order


# 11/8. Regular vs promo stay separate; promo precedence ----------------------
async def test_promotion_overlays_without_touching_regular():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        s.add(PricingPromotion(item_code=code, name="Flash", promo_price=base / 2, market="AE",
                               active=True))
        await s.commit()
        resolver.invalidate()
        eff = await resolver.get_effective_price(s, code)
        assert eff["price_source"] == "promotion" and eff["effective_price"] == base / 2
        # Base/published price unchanged underneath.
        cur = await pm.get_current_published(s)
        item = next(i for i in await pm.version_items(s, cur.id) if i.item_code == code)
        assert item.current_price == base


# 12/13. Promotion window: future=off, expired=off ---------------------------
async def test_promotion_window_activation_and_expiry():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        now = datetime.now(timezone.utc)
        s.add(PricingPromotion(item_code=code, name="Future", promo_price=1.0, market="AE",
                               active=True, starts_at=now + timedelta(days=1)))
        s.add(PricingPromotion(item_code=code, name="Past", promo_price=2.0, market="AE",
                               active=True, ends_at=now - timedelta(days=1)))
        await s.commit()
        resolver.invalidate()
        eff = await resolver.get_effective_price(s, code)
        # Neither window is active now → falls back to published base.
        assert eff["price_source"] == "published" and eff["effective_price"] == base


# 14/15. Starting / inspection never become a firm total ----------------------
async def test_starting_and_inspection_stay_pending():
    code = _starting_code()
    if not code:
        return
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        eff = await resolver.get_effective_price(s, code)
        assert eff["price_source"] in ("starting", "pending")


# 21/22. Rollback restores + audits ------------------------------------------
async def test_rollback_restores_previous_and_audits():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        await _publish_price_change(s, code, base + 500)  # v2
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base + 500
        await pm.rollback_to(s, target_version_number=1, actor="admin@x", reason="oops")
        await s.commit()
        resolver.invalidate()
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base
        from sqlalchemy import select
        rows = (await s.execute(
            select(PricingAuditLog).where(PricingAuditLog.action == "rollback"))).scalars().all()
        assert rows  # a rollback audit row exists


# 25. Duplicate item codes rejected (validation) -----------------------------
async def test_duplicate_item_codes_rejected():
    async with AsyncSessionLocal() as s:
        draft = await pm.create_draft(s, actor="a@x")  # ensures v1 then a draft
        # Force a duplicate.
        items = await pm.version_items(s, draft.id)
        dup = CatalogueVersionItem(version_id=draft.id, item_code=items[0].item_code,
                                   canonical_name="Dup", pricing_type="FIXED_PER_ITEM",
                                   pricing_unit="ITEM", current_price=1)
        s.add(dup)
        await s.flush()
        errs = await pm.validate_version(s, draft.id)
        assert any("Duplicate" in e for e in errs)


# 26. Concurrent edit detected (optimistic lock) -----------------------------
async def test_concurrent_edit_detected():
    async with AsyncSessionLocal() as s:
        draft = await pm.create_draft(s, actor="a@x")
        await s.commit()
        code = _exact_code()
        try:
            await pm.update_draft_item(s, version_id=draft.id, item_code=code,
                                       changes={"current_price": 5}, actor="a@x",
                                       expected_updated="1999-01-01 00:00:00")
            assert False, "expected conflict"
        except pm.PricingError as e:
            assert "changed since" in str(e)


# 29. Exactly one atomic current version at a time ---------------------------
async def test_only_one_current_version():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        await _publish_price_change(s, code, 10)
        await _publish_price_change(s, code, 20)
        from sqlalchemy import select
        currents = (await s.execute(
            select(CatalogueVersion).where(CatalogueVersion.is_current.is_(True)))).scalars().all()
        assert len(currents) == 1 and currents[0].status == "published"


# 2/3. Permissions: operations cannot publish; admin can ----------------------
def test_permission_mapping():
    assert perms.can("admin", perms.PUBLISH) and perms.can("admin", perms.ROLLBACK)
    assert perms.can("operations", perms.VIEW) and perms.can("operations", perms.CREATE)
    assert not perms.can("operations", perms.PUBLISH)
    assert not perms.can("operations", perms.ROLLBACK)
    assert not perms.can("operations", perms.IMPORT)


class _AuthOn:
    require_auth = True
    jwt_secret_effective = "pricing-test-secret"


def _req(token=None):
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "headers": headers})


async def test_operations_publish_guard_403(monkeypatch):
    from api import deps
    from services import auth as auth_svc
    monkeypatch.setattr(deps, "get_settings", lambda: _AuthOn())
    # pricing_permissions.require_pricing imports get_settings from settings; patch there too.
    import settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_settings", lambda: _AuthOn())
    ops = auth_svc.create_access_token(subject="u", role="operations", email="o@x",
                                       secret="pricing-test-secret")
    dep = perms.require_pricing(perms.PUBLISH)
    try:
        await dep(_req(ops))
        assert False, "expected 403"
    except Exception as e:
        assert getattr(e, "status_code", None) == 403


# 8 (engine). Agent pricing engine uses published/promo overrides -------------
async def test_calculate_estimate_uses_published_overrides():
    from services import pricing
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base_item = cat.item_by_code(code)
        # No override → static catalogue price.
        q0 = pricing.calculate_estimate([{"item_code": code, "quantity": 2}])
        assert q0.subtotal_excluding_vat == pricing._round(base_item["current_price"] * 2)
        # Override (as the published resolver would supply) → new price used.
        q1 = pricing.calculate_estimate([{"item_code": code, "quantity": 2}],
                                        price_overrides={code: 100.0})
        assert q1.subtotal_excluding_vat == 200.0
        # And the resolver produces such an override map from the published version.
        await _publish_price_change(s, code, 100.0)
        overrides = await resolver.published_overrides(s)
        assert overrides.get(code) == 100.0


# 12 (worker). Scheduled publish activates when due ---------------------------
async def test_scheduled_publish_activates_via_worker():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        draft = await pm.create_draft(s, actor="a@x")
        await pm.update_draft_item(s, version_id=draft.id, item_code=code,
                                   changes={"current_price": base + 321}, actor="a@x")
        now = datetime.now(timezone.utc)
        # Scheduled for the future → stays PENDING (not yet live).
        await pm.publish_version(s, version_id=draft.id, actor="a@x",
                                 effective_at=now + timedelta(hours=1))
        await s.commit()
        resolver.invalidate()
        assert draft.status == "pending_review"
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base
        # Worker runs after the effective time → activates it.
        res = await pm.apply_scheduled(s, now=now + timedelta(hours=2))
        await s.commit()
        resolver.invalidate()
        assert draft.version_number in res["activated_versions"]
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base + 321


# 24. Import creates a DRAFT, never changes live pricing ----------------------
async def test_import_creates_draft_only():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        base = (await resolver.get_effective_price(s, code))["effective_price"]
        draft = await pm.create_draft(s, actor="imp@x", source="import")
        await pm.update_draft_item(s, version_id=draft.id, item_code=code,
                                   changes={"current_price": base + 1000}, actor="imp@x")
        await s.commit()
        resolver.invalidate()
        # Live/published price is unchanged — the import is only a draft.
        assert (await resolver.get_effective_price(s, code))["effective_price"] == base
        assert draft.status == "draft" and draft.source == "import"


# DoD. Live booking-FSM uses published overrides (no restart) ----------------
async def test_booking_flow_uses_published_overrides():
    from services import booking_flow as bf
    code = _exact_code()
    # advance() sets this per turn from resolver.published_overrides(); simulate it.
    token = bf._PRICE_OVERRIDES.set({code: 250.0})
    try:
        updates = bf._pricing_updates([{"item_code": code, "quantity": 1}], "CAT", "Cat")
    finally:
        bf._PRICE_OVERRIDES.reset(token)
    assert updates["subtotal_amount"] == 250.0  # published override used, not catalogue price
    # Without the override the static catalogue price is used (unchanged behaviour).
    static = bf._pricing_updates([{"item_code": code, "quantity": 1}], "CAT", "Cat")
    assert static["subtotal_amount"] == cat.item_by_code(code)["current_price"]


# 27/28. Public API excludes disabled items ----------------------------------
async def test_public_excludes_disabled_items():
    async with AsyncSessionLocal() as s:
        await pm.ensure_initial_version(s)
        await s.commit()
        code = _exact_code()
        # Deactivate an item in a draft, publish.
        draft = await pm.create_draft(s, actor="a@x")
        await pm.update_draft_item(s, version_id=draft.id, item_code=code,
                                   changes={"active": False}, actor="a@x")
        await pm.publish_version(s, version_id=draft.id, actor="a@x")
        await s.commit()
        resolver.invalidate()
        pub = await resolver.get_published_catalogue(s, public=True)
        assert all(i["item_code"] != code for i in pub["items"])
