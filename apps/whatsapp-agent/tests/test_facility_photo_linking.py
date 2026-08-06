"""Per-item photo linking — scoped relink SQL, upload passthrough, endpoint (Area 4)."""
import pytest

from db import database
from db.repositories import order_photos_repo
from services import order_photos as photo_svc


# ----------------------------- repo relink -------------------------------
async def test_set_item_link_is_facility_scoped(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "p1", "order_id": "o1", "order_item_id": "li-1", "facility_id": "F1",
                "stage": "intake"}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await order_photos_repo.set_item_link("p1", "F1", order_item_id="li-1")
    assert "facility_id = $2" in captured["sql"]
    assert "deleted_at is null" in captured["sql"]
    assert captured["args"][1] == "F1"
    assert captured["args"][2] == "li-1"


async def test_set_item_link_unlink_passes_null(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["args"] = args
        return {"id": "p1", "order_id": "o1", "order_item_id": None, "facility_id": "F1"}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await order_photos_repo.set_item_link("p1", "F1", order_item_id=None)
    assert captured["args"][2] is None  # unlinks back to general order photos


# ------------------------- service link + audit --------------------------
async def test_link_photo_to_item_returns_none_for_other_facility(monkeypatch):
    async def none_link(pid, fid, *, order_item_id, caption=None):
        return None

    monkeypatch.setattr(order_photos_repo, "set_item_link", none_link)
    out = await photo_svc.link_photo_to_item("p1", "F-OTHER", order_item_id="li-1")
    assert out is None  # not this facility's photo → no relink, no leak


async def test_link_photo_to_item_writes_audit(monkeypatch):
    events = {}

    async def ok_link(pid, fid, *, order_item_id, caption=None):
        return {"id": "p1", "order_id": "o1", "order_item_id": order_item_id, "stage": "intake",
                "storage_key": "k", "content_type": "image/jpeg", "file_name": "f.jpg"}

    async def fake_event(**kwargs):
        events.update(kwargs)
        return {}

    monkeypatch.setattr(order_photos_repo, "set_item_link", ok_link)
    monkeypatch.setattr(photo_svc.order_events_repo, "create", fake_event)
    out = await photo_svc.link_photo_to_item("p1", "F1", order_item_id="li-1", actor_name="Jane")
    assert out["order_item_id"] == "li-1"
    assert "storage_key" not in out  # PII-safe view
    assert events["event_type"] == "order_photo_relinked"


# --------------------------- upload passthrough --------------------------
async def test_upload_infers_source_and_links_item(monkeypatch):
    created = {}

    async def fake_count(order_uuid, stage):
        return 0

    async def fake_upload(**kwargs):
        return {"provider": "local", "object_key": "k", "bucket": None, "public_url": None}

    async def fake_create(**kwargs):
        created.update(kwargs)
        return {"id": "p1", "order_id": kwargs["order_uuid"], "stage": kwargs["stage"],
                "order_item_id": kwargs.get("order_item_id"), "source": kwargs.get("source"),
                "content_type": "image/jpeg", "file_name": "f.jpg"}

    async def fake_event(**kwargs):
        return {}

    monkeypatch.setattr(order_photos_repo, "count_for_stage", fake_count)
    monkeypatch.setattr(order_photos_repo, "create", fake_create)
    monkeypatch.setattr(photo_svc.media_storage, "upload_file", fake_upload)
    monkeypatch.setattr(photo_svc.media_storage, "sha256_hex", lambda d: "abc")
    monkeypatch.setattr(photo_svc.order_events_repo, "create", fake_event)

    jpeg = b"\xff\xd8\xff" + b"\x00" * 20
    out = await photo_svc.add_photos(
        order_uuid="o1", facility_id="F1", stage="intake",
        files=[photo_svc.IncomingPhoto("a.jpg", "image/jpeg", jpeg)],
        order_item_id="li-1",
    )
    assert len(out) == 1
    assert created["order_item_id"] == "li-1"
    # source inferred from stage when not supplied.
    assert created["source"] == "FACILITY_BEFORE_PROCESSING"
