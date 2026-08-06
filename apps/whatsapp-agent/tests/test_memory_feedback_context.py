"""Memory service orchestration + feedback capture + order-context resolution."""
import pytest

from db import database
from services import customer_memory_service as mem_svc
from services import customer_feedback_service as fb_svc
from services import order_context as ctx


# ------------------------------ memory service ---------------------------
async def test_save_new_memory_inserts(monkeypatch):
    calls = {}

    async def list_active(cid):
        return []

    async def insert(**kw):
        calls["insert"] = kw
        return {"id": "m1", **kw, "status": "active"}

    monkeypatch.setattr(mem_svc.repo, "list_active", list_active)
    monkeypatch.setattr(mem_svc.repo, "insert", insert)
    out = await mem_svc.save_confirmed_customer_memory(
        "C1", memory_type="NAME", memory_key="name", memory_value="Zoya", customer_confirmed=True)
    assert out["action"] == "created" and calls["insert"]["memory_value"] == "Zoya"


async def test_save_rejects_null_and_unconfirmed(monkeypatch):
    async def list_active(cid):
        return []
    monkeypatch.setattr(mem_svc.repo, "list_active", list_active)
    r1 = await mem_svc.save_confirmed_customer_memory("C1", memory_type="ADDRESS", memory_key="addr",
                                                      memory_value=None, customer_confirmed=True)
    assert r1["action"] == "reject"
    r2 = await mem_svc.save_confirmed_customer_memory("C1", memory_type="NAME", memory_key="name",
                                                      memory_value="Guess", customer_confirmed=False)
    assert r2["action"] == "reject" and r2["reason"] == "not_customer_confirmed"


async def test_correction_supersedes_and_writes_history(monkeypatch):
    calls = {"superseded": [], "history": []}

    async def list_active(cid):
        return [{"id": "m1", "memory_key": "address", "scope": mem_svc.policy.CUSTOMER_GLOBAL,
                 "memory_value": "Apartment 403", "status": "active"}]

    async def mark_superseded(mid):
        calls["superseded"].append(mid)

    async def add_history(**kw):
        calls["history"].append(kw)

    async def insert(**kw):
        return {"id": "m2", **kw, "status": "active"}

    monkeypatch.setattr(mem_svc.repo, "list_active", list_active)
    monkeypatch.setattr(mem_svc.repo, "mark_superseded", mark_superseded)
    monkeypatch.setattr(mem_svc.repo, "add_history", add_history)
    monkeypatch.setattr(mem_svc.repo, "insert", insert)
    out = await mem_svc.save_confirmed_customer_memory(
        "C1", memory_type="ADDRESS", memory_key="address", memory_value="Apartment 904",
        scope=mem_svc.policy.CUSTOMER_GLOBAL, customer_confirmed=True)
    assert out["action"] == "updated"
    assert calls["superseded"] == ["m1"]
    assert calls["history"][0]["old_value"] == "Apartment 403" and calls["history"][0]["new_value"] == "Apartment 904"


# ------------------------------ feedback service -------------------------
async def test_feedback_capture_persists_detected_events(monkeypatch):
    created = []

    async def create(**kw):
        created.append(kw)
        return {"id": f"f{len(created)}", **kw}

    monkeypatch.setattr(fb_svc.repo, "create", create)
    out = await fb_svc.create_customer_feedback_event(
        "My name is Zoya, not Zoha", customer_id="C1", provider="evolution", provider_message_id="m1")
    assert len(out) >= 1
    assert any(c["feedback_type"] == "NAME_CORRECTION" and c["scope"] == "customer" for c in created)


async def test_feedback_idempotent_duplicate(monkeypatch):
    async def create(**kw):
        return None  # unique conflict → duplicate

    monkeypatch.setattr(fb_svc.repo, "create", create)
    out = await fb_svc.create_customer_feedback_event(
        "Your replies are always too long", customer_id="C1", provider="evolution", provider_message_id="m1")
    assert out == []  # nothing new created


# --------------------------- order-context resolver ----------------------
def test_explicit_ref_resolves():
    cands = [{"order_id": "o1", "order_ref": "LK-AE-1024", "status": "active"},
             {"order_id": "o2", "order_ref": "LK-AE-1040", "status": "active"}]
    out = ctx.resolve_order_context(candidates=cands, explicit_ref="LK-AE-1040")
    assert out["order_id"] == "o2" and out["ambiguous"] is False and out["resolution"] == "explicit"


def test_single_active_resolves():
    out = ctx.resolve_order_context(candidates=[{"order_id": "o1", "order_ref": "LK-1", "status": "active"}])
    assert out["order_id"] == "o1" and out["resolution"] == "single_active"


def test_two_active_ambiguous_asks_one_question():
    cands = [{"order_id": "o1", "order_ref": "LK-AE-1024", "status": "active"},
             {"order_id": "o2", "order_ref": "LK-AE-1040", "status": "active"}]
    out = ctx.resolve_order_context(candidates=cands)
    assert out["ambiguous"] is True and out["order_id"] is None
    assert "LK-AE-1024" in out["clarification_question"] and "LK-AE-1040" in out["clarification_question"]


def test_no_active_orders():
    out = ctx.resolve_order_context(candidates=[{"order_id": "o1", "order_ref": "LK-1", "status": "completed"}])
    assert out["resolution"] == "none" and out["order_id"] is None


async def test_link_media_records_order_and_item(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "l1", "order_id": args[2], "order_item_id": args[3], "media_id": args[5],
                "provider_message_id": args[4], "link_type": "media", "created_at": "t"}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await ctx.link_media_to_order(media_id="p1", order_id="oA", order_item_id="li-1",
                                        provider_message_id="msg1", media_purpose="stain_reference")
    assert "insert into order_context_links" in captured["sql"]
    assert out["order_id"] == "oA" and out["order_item_id"] == "li-1"
