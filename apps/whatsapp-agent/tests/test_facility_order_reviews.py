"""Review-acknowledgement repo idempotency + backend Start-Processing gate.

Supabase-only paths are exercised by monkeypatching the DB layer / repos rather
than hitting Postgres (the suite runs on SQLite), matching test_facility_orders.py.
"""
import pytest

from db import database
from db.repositories import (
    facility_order_reviews_repo as reviews_repo,
    order_notes_repo,
    order_photos_repo,
)
from services import facility_orders as svc


# --------------------------- repo idempotency ----------------------------
async def test_acknowledge_is_idempotent_by_content(monkeypatch):
    existing = {"order_version": 0, "notes_version": 3, "photo_version": 1,
                "invalidated_at": None, "acknowledged_at": "t0"}

    async def fake_latest(fid, ouid):
        return existing

    async def boom(*a, **k):  # an insert here would be a duplicate ack
        raise AssertionError("must not insert a duplicate acknowledgement")

    monkeypatch.setattr(reviews_repo, "latest_for_order", fake_latest)
    monkeypatch.setattr(database, "fetchrow", boom)
    out = await reviews_repo.acknowledge(
        facility_id="F1", order_uuid="O1", facility_user_id="u1",
        order_version=0, notes_version=3, photo_version=1,
    )
    assert out is existing  # returned the existing row, no new write


async def test_acknowledge_inserts_when_versions_differ(monkeypatch):
    captured = {}

    async def fake_latest(fid, ouid):
        return {"order_version": 0, "notes_version": 2, "photo_version": 0, "invalidated_at": None}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "rev-1", "order_id": ouid_marker, "facility_id": "F1",
                "facility_user_id": "u1", "order_version": 0, "notes_version": 3,
                "photo_version": 1, "acknowledged_at": "t1", "invalidated_at": None,
                "invalidation_reason": None}

    ouid_marker = "O1"
    monkeypatch.setattr(reviews_repo, "latest_for_order", fake_latest)
    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await reviews_repo.acknowledge(
        facility_id="F1", order_uuid="O1", facility_user_id="u1",
        order_version=0, notes_version=3, photo_version=1,
    )
    assert "insert into facility_order_reviews" in captured["sql"]
    assert out["notes_version"] == 3 and out["photo_version"] == 1


async def test_latest_for_order_is_facility_scoped(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await reviews_repo.latest_for_order("F-XYZ", "O1")
    assert "facility_id = $1" in captured["sql"]
    assert captured["args"][0] == "F-XYZ"


# --------------------------- backend start-processing gate ---------------
async def test_review_is_current_false_when_no_ack(monkeypatch):
    async def notes_all(_):
        return [{"id": "n1"}, {"id": "n2"}]

    async def photos(_):
        return [{"id": "p1"}]

    async def latest(fid, ouid):
        return None

    monkeypatch.setattr(order_notes_repo, "list_all", notes_all)
    monkeypatch.setattr(order_photos_repo, "list_for_order", photos)
    monkeypatch.setattr(reviews_repo, "latest_for_order", latest)
    assert await svc._review_is_current("F1", "O1") is False


async def test_review_is_current_true_when_versions_match(monkeypatch):
    async def notes_all(_):
        return [{"id": "n1"}, {"id": "n2"}]

    async def photos(_):
        return [{"id": "p1"}]

    async def latest(fid, ouid):
        return {"notes_version": 2, "photo_version": 1, "order_version": 0, "invalidated_at": None}

    monkeypatch.setattr(order_notes_repo, "list_all", notes_all)
    monkeypatch.setattr(order_photos_repo, "list_for_order", photos)
    monkeypatch.setattr(reviews_repo, "latest_for_order", latest)
    assert await svc._review_is_current("F1", "O1") is True


async def test_start_cleaning_blocked_until_review_acknowledged(monkeypatch):
    async def fake_get_row(facility_id, order_id):
        return {"id": "u1", "status": "picked_up", "order_id": order_id}

    async def not_current(fid, ouid):
        return False

    monkeypatch.setattr(svc.facility_orders_repo, "get_row", fake_get_row)
    monkeypatch.setattr(svc, "_review_is_current", not_current)
    with pytest.raises(svc.ReviewNotAcknowledged):
        await svc.apply_action("F1", "LK-1", "start_cleaning", actor_label="Owner")


async def test_illegal_transition_still_fails_before_review_gate(monkeypatch):
    # start_cleaning from 'completed' must raise Invalid (status) not ReviewNot… .
    async def fake_get_row(facility_id, order_id):
        return {"id": "u1", "status": "completed", "order_id": order_id}

    monkeypatch.setattr(svc.facility_orders_repo, "get_row", fake_get_row)
    with pytest.raises(svc.InvalidFacilityAction):
        await svc.apply_action("F1", "LK-1", "start_cleaning", actor_label="Owner")
