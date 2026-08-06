"""Blocking-issue gate: an order can't advance to ready/handoff while a blocking
issue (price revision / customer response) is open (Area 5)."""
import pytest

from db import database
from db.repositories import facility_issues_repo
from services import facility_orders as svc


async def test_has_blocking_open_issue_sql_scopes_order_and_flags(monkeypatch):
    captured = {}

    async def fake_fetchval(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return True

    monkeypatch.setattr(database, "fetchval", fake_fetchval)
    out = await facility_issues_repo.has_blocking_open_issue("O1")
    assert out is True
    assert "order_id = $1" in captured["sql"]
    assert "requires_price_revision" in captured["sql"]
    assert "requires_customer_response" in captured["sql"]
    assert "not in ('resolved','closed')" in captured["sql"]


async def test_mark_ready_blocked_by_open_issue(monkeypatch):
    async def get_row(fid, oid):
        return {"id": "u1", "status": "in_cleaning", "order_id": oid}

    async def blocking(order_uuid):
        return True

    monkeypatch.setattr(svc.facility_orders_repo, "get_row", get_row)
    monkeypatch.setattr(svc.facility_issues_repo, "has_blocking_open_issue", blocking)
    with pytest.raises(svc.ProcessingBlocked):
        await svc.apply_action("F1", "LK-1", "mark_ready", actor_label="Owner")


async def test_start_cleaning_is_not_issue_gated(monkeypatch):
    # start_cleaning is review-gated, NOT issue-gated — a blocking issue must not
    # be consulted for it (the review gate runs first and passes here).
    called = {"issue": False}

    async def get_row(fid, oid):
        return {"id": "u1", "status": "picked_up", "order_id": oid}

    async def review_ok(fid, ouid):
        return True

    async def blocking(order_uuid):
        called["issue"] = True
        return True

    async def fake_fetchrow(sql, *a):
        return {"id": "u1"}

    async def fake_event(**k):
        return {}

    async def fake_get(fid, oid):
        return {"order_id": oid, "status": "in_cleaning"}

    async def fake_notify(*a, **k):
        return None

    monkeypatch.setattr(svc.facility_orders_repo, "get_row", get_row)
    monkeypatch.setattr(svc, "_review_is_current", review_ok)
    monkeypatch.setattr(svc.facility_issues_repo, "has_blocking_open_issue", blocking)
    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    monkeypatch.setattr(svc.order_events_repo, "create", fake_event)
    monkeypatch.setattr(svc.facility_orders_repo, "get", fake_get)
    monkeypatch.setattr(svc.facility_notify, "notify_order_status_updated", fake_notify)

    await svc.apply_action("F1", "LK-1", "start_cleaning", actor_label="Owner")
    assert called["issue"] is False  # issue gate not consulted for start_cleaning
