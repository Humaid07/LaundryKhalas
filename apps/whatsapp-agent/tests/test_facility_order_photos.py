"""Facility order-photo tests — scoping, validation, storage, audit, privacy.

The Supabase-only DB paths are exercised WITHOUT Postgres (the suite runs on
SQLite): endpoint functions are called directly with a hand-built principal dict
(exactly what ``require_facility_scope`` would produce) and the repo/storage/event
layers are monkeypatched. This mirrors tests/test_facility_orders.py.
"""
import pytest
from fastapi import HTTPException

import api.facility_order_photos as api_photos
import api.orders as api_orders
from db import database
from db.repositories import facility_orders_repo, order_events_repo, order_photos_repo, orders_repo
from services import order_photos as svc


# --------------------------- fixtures / helpers ---------------------------
def _jpeg(size: int = 64) -> bytes:
    """Minimal bytes that sniff as JPEG (FF D8 FF …), padded to >= 12 bytes."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * max(8, size)


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _FakeUpload:
    """Stand-in for starlette UploadFile (async .read + filename/content_type)."""

    def __init__(self, data: bytes, filename: str, content_type: str):
        self._d, self.filename, self.content_type = data, filename, content_type

    async def read(self) -> bytes:
        return self._d


@pytest.fixture
def wired(monkeypatch):
    """Supabase-mode ON + storage/repo/events captured (no disk, no Postgres)."""
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    created: list[dict] = []
    events: list[dict] = []

    async def fake_create(**kw):
        created.append(kw)
        return {"id": f"photo-{len(created)}", "order_id": kw["order_uuid"],
                "stage": kw["stage"], "file_name": kw["file_name"],
                "content_type": kw["content_type"], "file_size": kw["file_size"],
                "uploaded_by_name": kw.get("uploaded_by_name"), "public_url": None,
                "created_at": "2026-07-30T10:00:00Z"}

    async def fake_count(order_uuid, stage):
        return 0

    async def fake_event(**kw):
        events.append(kw)
        return {"id": "evt-1", **kw}

    def fake_save(order_uuid, ext, data):
        return (f"{order_uuid}/order-photo-abc.{ext}", f"order-photo-abc.{ext}")

    monkeypatch.setattr(order_photos_repo, "create", fake_create)
    monkeypatch.setattr(order_photos_repo, "count_for_stage", fake_count)
    monkeypatch.setattr(order_events_repo, "create", fake_event)
    monkeypatch.setattr(svc, "_save_local", fake_save)
    return {"created": created, "events": events, "monkeypatch": monkeypatch}


def _principal(role="facility_owner", fid="fac-mine"):
    return {"id": "u1", "role": role, "facility_id": fid, "full_name": "Owner Jane"}


# ============================ service layer ================================
async def test_upload_intake_creates_row_and_event(wired):
    photos = await svc.add_photos(
        order_uuid="ord-1", facility_id="fac-mine", stage="intake",
        files=[svc.IncomingPhoto("a.jpg", "image/jpeg", _jpeg())],
        actor_id="u1", actor_name="Owner Jane",
    )
    assert len(photos) == 1                                   # (1) intake ok
    assert len(wired["created"]) == 1                         # (6) order_photos row
    assert wired["created"][0]["stage"] == "intake"
    assert len(wired["events"]) == 1                          # (7) order event
    assert wired["events"][0]["event_type"] == "intake_photos_uploaded"
    assert wired["events"][0]["metadata"]["photo_count"] == 1


async def test_upload_pre_dispatch_event_type(wired):
    await svc.add_photos(
        order_uuid="ord-1", facility_id="fac-mine", stage="pre_dispatch",
        files=[svc.IncomingPhoto("b.png", "image/png", _png())],
        actor_name="Owner Jane",
    )
    assert wired["events"][0]["event_type"] == "pre_dispatch_photos_uploaded"  # (2)


async def test_invalid_file_type_rejected(wired):
    with pytest.raises(svc.PhotoValidationError) as exc:                       # (4)
        await svc.add_photos(
            order_uuid="ord-1", facility_id="fac-mine", stage="intake",
            files=[svc.IncomingPhoto("x.pdf", "application/pdf", b"%PDF-1.4 ....")],
        )
    assert exc.value.status_code == 415
    assert not wired["created"] and not wired["events"]        # nothing stored


async def test_svg_is_rejected(wired):
    # SVG is script-carrying and must be blocked even if labelled as an image.
    with pytest.raises(svc.PhotoValidationError):
        await svc.add_photos(
            order_uuid="ord-1", facility_id="fac-mine", stage="intake",
            files=[svc.IncomingPhoto("x.svg", "image/svg+xml", b"<svg></svg>")],
        )


async def test_content_type_spoof_rejected(wired):
    # Declared image/jpeg but the bytes are not a JPEG → magic-byte check rejects.
    with pytest.raises(svc.PhotoValidationError) as exc:
        await svc.add_photos(
            order_uuid="ord-1", facility_id="fac-mine", stage="intake",
            files=[svc.IncomingPhoto("evil.jpg", "image/jpeg", b"MZ\x90\x00 not an image")],
        )
    assert exc.value.status_code == 415


async def test_oversized_file_rejected(wired):
    big = _jpeg(6 * 1024 * 1024)  # > 5MB default ceiling
    with pytest.raises(svc.PhotoValidationError) as exc:                       # (5)
        await svc.add_photos(
            order_uuid="ord-1", facility_id="fac-mine", stage="intake",
            files=[svc.IncomingPhoto("big.jpg", "image/jpeg", big)],
        )
    assert exc.value.status_code == 413


async def test_per_stage_cap_enforced(wired):
    async def full(order_uuid, stage):
        return 10  # already at the default per-stage max
    wired["monkeypatch"].setattr(order_photos_repo, "count_for_stage", full)
    with pytest.raises(svc.PhotoValidationError) as exc:
        await svc.add_photos(
            order_uuid="ord-1", facility_id="fac-mine", stage="intake",
            files=[svc.IncomingPhoto("a.jpg", "image/jpeg", _jpeg())],
        )
    assert exc.value.status_code == 409


async def test_stored_metadata_has_no_customer_pii(wired):
    await svc.add_photos(
        order_uuid="ord-1", facility_id="fac-mine", stage="intake",
        files=[svc.IncomingPhoto("Ahmed-0501234567.jpg", "image/jpeg", _jpeg())],
        actor_name="Owner Jane",
    )
    row = wired["created"][0]
    # (10) file name is generated (never the client's PII-laden name); metadata is
    # stage-only; no customer field is persisted anywhere on the row.
    assert row["file_name"].startswith("order-photo-")
    assert "Ahmed" not in row["file_name"] and "0501234567" not in row["file_name"]
    assert set(row["metadata"].keys()) == {"stage"}
    blob = str(row)
    for pii in ("phone", "customer", "address", "email"):
        assert pii not in blob.lower()


def test_serializer_is_pii_safe():
    raw = {"id": "p1", "order_id": "o1", "facility_id": "f1", "stage": "intake",
           "storage_key": "o1/order-photo-x.jpg", "public_url": None,
           "file_name": "order-photo-x.jpg", "content_type": "image/jpeg",
           "file_size": 1234, "uploaded_by_user_id": "u1",
           "uploaded_by_name": "Owner Jane", "created_at": "t"}
    out = order_photos_repo.to_read(raw)
    # storage_key + user id are internal and must never surface.
    assert "storage_key" not in out and "uploaded_by_user_id" not in out
    assert out["uploaded_by"] == "Owner Jane" and out["id"] == "p1"


# ============================ endpoint layer ==============================
async def test_cannot_upload_for_another_facility(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def no_row(fid, order_id):                 # scoped lookup finds nothing
        return None
    monkeypatch.setattr(facility_orders_repo, "get_row", no_row)

    with pytest.raises(HTTPException) as exc:        # (3) other facility → 404
        await api_photos.upload_order_photos(
            "SOMEONE-ELSE-ORDER", stage="intake",
            files=[_FakeUpload(_jpeg(), "a.jpg", "image/jpeg")],
            principal=_principal(fid="fac-mine"),
        )
    assert exc.value.status_code == 404


async def test_list_is_scoped_to_caller_facility(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    seen = {}

    async def get_row(fid, order_id):
        seen["fid"] = fid
        return {"id": "ord-uuid-1"}
    async def list_photos(order_uuid, stage=None):
        return [{"id": "p1", "stage": "intake"}, {"id": "p2", "stage": "intake"}]

    monkeypatch.setattr(facility_orders_repo, "get_row", get_row)
    monkeypatch.setattr(svc, "list_photos", list_photos)

    res = await api_photos.list_order_photos("LK-1", principal=_principal(fid="fac-A"))
    assert seen["fid"] == "fac-A"                     # (8) always scoped by principal
    assert res["counts"]["intake"] == 2


async def test_delete_soft_deletes_and_requires_manage(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def get_row(fid, order_id):
        return {"id": "ord-uuid-1"}
    monkeypatch.setattr(facility_orders_repo, "get_row", get_row)

    # Staff role cannot manage → 403 before any delete.
    with pytest.raises(HTTPException) as exc:
        await api_photos.delete_order_photo(
            "LK-1", "p1", principal=_principal(role="facility_staff"))
    assert exc.value.status_code == 403

    # Owner can; delete_photo returning None (not theirs) → 404, else ok.
    async def del_none(pid, fid, actor_name=None):
        return None
    monkeypatch.setattr(svc, "delete_photo", del_none)
    with pytest.raises(HTTPException) as exc2:
        await api_photos.delete_order_photo("LK-1", "p1", principal=_principal())
    assert exc2.value.status_code == 404             # (9) scoped soft-delete

    async def del_ok(pid, fid, actor_name=None):
        return {"id": pid}
    monkeypatch.setattr(svc, "delete_photo", del_ok)
    res = await api_photos.delete_order_photo("LK-1", "p1", principal=_principal())
    assert res == {"deleted": True, "id": "p1"}


async def test_upload_maps_validation_error_to_status(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def get_row(fid, order_id):
        return {"id": "ord-uuid-1"}
    monkeypatch.setattr(facility_orders_repo, "get_row", get_row)

    with pytest.raises(HTTPException) as exc:         # bad type surfaces as 415
        await api_photos.upload_order_photos(
            "LK-1", stage="intake",
            files=[_FakeUpload(b"%PDF", "x.pdf", "application/pdf")],
            principal=_principal(),
        )
    assert exc.value.status_code == 415


# ===================== internal ops read-only view =========================
async def test_ops_photos_list_counts_by_stage(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def get_read(order_id):
        return {"id": "ord-uuid-1"}
    async def list_photos(order_uuid, stage=None):
        return [{"id": "p1", "stage": "intake"}, {"id": "p2", "stage": "intake"},
                {"id": "p3", "stage": "pre_dispatch"}]
    monkeypatch.setattr(orders_repo, "get_read", get_read)
    monkeypatch.setattr(svc, "list_photos", list_photos)

    res = await api_orders.order_photos_list("LK-ANY")   # ops see any facility's order
    assert res["counts"] == {"intake": 2, "pre_dispatch": 1}
    assert len(res["photos"]) == 3


async def test_ops_photo_content_requires_matching_order(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def get_read(order_id):
        return {"id": "ord-uuid-1"}
    monkeypatch.setattr(orders_repo, "get_read", get_read)

    # read_content_by_id returns None when the photo isn't on this order → 404.
    async def none_content(photo_id, *, order_uuid=None):
        return None
    monkeypatch.setattr(svc, "read_content_by_id", none_content)
    with pytest.raises(HTTPException) as exc:
        await api_orders.order_photo_content("LK-ANY", "p1")
    assert exc.value.status_code == 404


async def test_ops_photo_content_by_id_scopes_to_order(monkeypatch):
    # Service-level: get_any returns a row for another order → None when order_uuid differs.
    async def get_any(photo_id):
        return {"id": photo_id, "order_id": "other-order", "storage_key": "k/x.jpg",
                "content_type": "image/jpeg", "file_name": "order-photo-x.jpg"}
    monkeypatch.setattr(order_photos_repo, "get_any", get_any)
    assert await svc.read_content_by_id("p1", order_uuid="ord-uuid-1") is None
