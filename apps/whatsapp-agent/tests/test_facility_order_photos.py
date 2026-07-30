"""Facility order-photo tests — scoping, validation, storage, audit, privacy.

The Supabase-only DB paths are exercised WITHOUT Postgres (the suite runs on
SQLite): endpoint functions are called directly with a hand-built principal dict
(exactly what ``require_facility_scope`` would produce) and the repo/storage/event
layers are monkeypatched. This mirrors tests/test_facility_orders.py.
"""
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.facility_order_photos as api_photos
import api.orders as api_orders
from db import database
from db.repositories import facility_orders_repo, order_events_repo, order_photos_repo, orders_repo
from services import media_storage
from services import order_photos as svc
from settings import Settings


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

    uploaded: list[dict] = []

    async def fake_upload(*, object_key, data, content_type, provider=None):
        uploaded.append({"object_key": object_key, "content_type": content_type, "size": len(data)})
        return {"provider": "local", "bucket": None, "object_key": object_key, "public_url": None}

    monkeypatch.setattr(order_photos_repo, "create", fake_create)
    monkeypatch.setattr(order_photos_repo, "count_for_stage", fake_count)
    monkeypatch.setattr(order_events_repo, "create", fake_event)
    # Capture storage writes at the media_storage boundary (no disk, no network).
    monkeypatch.setattr(media_storage, "upload_file", fake_upload)
    return {"created": created, "events": events, "uploaded": uploaded, "monkeypatch": monkeypatch}


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


# ==================== media storage service (R2 + local) ===================
def _r2_settings(**over):
    """A minimal settings stand-in exposing only what media_storage reads."""
    base = dict(
        media_storage_provider_normalized="r2",
        r2_is_configured=True,
        cloudflare_r2_bucket="lk-media",
        cloudflare_r2_region="auto",
        cloudflare_r2_endpoint="https://acct.r2.cloudflarestorage.com",
        cloudflare_r2_access_key_id="ak",
        cloudflare_r2_secret_access_key="sk",
        media_signed_url_expires_seconds=300,
        media_upload_signed_url_expires_seconds=300,
    )
    base.update(over)
    return SimpleNamespace(**base)


class _FakeR2:
    """Captures S3 calls without touching the network."""

    def __init__(self):
        self.put, self.deleted = [], []

    def put_object(self, **kw):
        self.put.append(kw)
        return {}

    def get_object(self, **kw):
        return {"Body": SimpleNamespace(read=lambda: b"IMG-BYTES")}

    def delete_object(self, **kw):
        self.deleted.append(kw)
        return {}

    def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
        return f"https://signed.example/{Params['Key']}?exp={ExpiresIn}"


def test_r2_config_loads():
    s = Settings(
        _env_file=None, media_storage_provider="r2",
        cloudflare_r2_account_id="acct", cloudflare_r2_bucket="lk-media",
        cloudflare_r2_endpoint="https://acct.r2.cloudflarestorage.com",
        cloudflare_r2_access_key_id="ak", cloudflare_r2_secret_access_key="sk",
    )
    assert s.media_storage_provider_normalized == "r2"
    assert s.r2_is_configured is True
    assert s.media_max_image_bytes == s.media_max_image_mb * 1024 * 1024
    assert "image/jpeg" in s.media_allowed_image_types_set


def test_missing_r2_config_flag_is_false():
    s = Settings(_env_file=None, media_storage_provider="r2")  # provider r2, no creds
    assert s.media_storage_provider_normalized == "r2"
    assert s.r2_is_configured is False


async def test_missing_r2_config_fails_safe_on_upload(monkeypatch):
    monkeypatch.setattr(media_storage, "get_settings", lambda: _r2_settings(r2_is_configured=False))
    media_storage.reset_client_cache()
    with pytest.raises(media_storage.MediaStorageError) as exc:
        await media_storage.upload_file(
            object_key="orders/AE/X/intake/a.jpg", data=_jpeg(), content_type="image/jpeg")
    assert exc.value.status_code == 503  # never a silent local fallback


async def test_r2_upload_read_and_sign(monkeypatch):
    fake = _FakeR2()
    monkeypatch.setattr(media_storage, "get_settings", lambda: _r2_settings())
    monkeypatch.setattr(media_storage, "_r2", lambda: fake)

    out = await media_storage.upload_file(
        object_key="orders/AE/LK-AE-1024/intake/a.jpg", data=_jpeg(), content_type="image/jpeg")
    assert out["provider"] == "r2" and out["bucket"] == "lk-media"
    assert fake.put and fake.put[0]["Key"] == "orders/AE/LK-AE-1024/intake/a.jpg"

    data = await media_storage.read_file(object_key="orders/AE/LK-AE-1024/intake/a.jpg", provider="r2")
    assert data == b"IMG-BYTES"

    url = await media_storage.create_signed_view_url(
        object_key="orders/AE/LK-AE-1024/intake/a.jpg", provider="r2")
    assert url.startswith("https://signed.example/") and "exp=300" in url


async def test_local_signed_view_url_is_none():
    assert await media_storage.create_signed_view_url(object_key="k.jpg", provider="local") is None


def test_validate_file_type_rejects_non_image_and_svg():
    allowed = {"image/jpeg", "image/png", "image/webp"}
    with pytest.raises(media_storage.MediaStorageError) as exc:
        media_storage.validate_file_type(declared_type="application/pdf", data=b"%PDF-1.4", allowed_types=allowed)
    assert exc.value.status_code == 415
    with pytest.raises(media_storage.MediaStorageError):  # SVG blocked
        media_storage.validate_file_type(declared_type="image/svg+xml", data=b"<svg></svg>", allowed_types=allowed)


def test_validate_file_type_accepts_jpeg():
    ct, ext = media_storage.validate_file_type(
        declared_type="image/jpeg", data=_jpeg(), allowed_types={"image/jpeg"})
    assert ct == "image/jpeg" and ext == "jpg"


def test_validate_file_size_rejects_oversized():
    with pytest.raises(media_storage.MediaStorageError) as exc:
        media_storage.validate_file_size(b"x" * 20, max_bytes=10)
    assert exc.value.status_code == 413


def test_checksum_is_sha256():
    assert media_storage.sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_object_key_is_pii_safe():
    key = svc._build_object_key(
        market_code="AE", order_ref="LK-AE-1024", order_uuid="ord-uuid", stage="intake", ext="jpg")
    assert key.startswith("orders/AE/LK-AE-1024/intake/") and key.endswith(".jpg")
    for pii in ("ahmed", "0501234567", "phone", "@", " "):
        assert pii not in key.lower()


async def test_upload_stores_pii_safe_key_and_checksum(wired):
    # Even with a PII-laden CLIENT filename, the stored object key + file name are
    # generated and carry only market/order-ref + uuids; checksum + provenance set.
    await svc.add_photos(
        order_uuid="ord-1", facility_id="fac-mine", stage="intake",
        market_code="AE", order_ref="LK-AE-1024",
        files=[svc.IncomingPhoto("Ahmed-0501234567.jpg", "image/jpeg", _jpeg())],
        actor_name="Owner Jane",
    )
    key = wired["uploaded"][0]["object_key"]
    assert key.startswith("orders/AE/LK-AE-1024/intake/")
    assert "Ahmed" not in key and "0501234567" not in key
    row = wired["created"][0]
    assert row["checksum_sha256"] == media_storage.sha256_hex(_jpeg())
    assert row["source_channel"] == "facility_dashboard" and row["visibility_scope"] == "facility"


# --------------- signed view-url endpoint (only after access check) --------
async def test_view_url_denied_for_other_facility(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def no_row(fid, order_id):
        return None
    monkeypatch.setattr(facility_orders_repo, "get_row", no_row)
    with pytest.raises(HTTPException) as exc:
        await api_photos.order_photo_view_url("LK-1", "p1", principal=_principal(fid="fac-mine"))
    assert exc.value.status_code == 404  # scope check first — never mints a URL


async def test_view_url_returns_signed_for_owner(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def get_row(fid, order_id):
        return {"id": "ord-uuid-1"}
    async def signed(photo_id, fid):
        return {"url": "https://signed.example/k.jpg?exp=300", "expires_in": 300, "provider": "r2"}
    monkeypatch.setattr(facility_orders_repo, "get_row", get_row)
    monkeypatch.setattr(svc, "signed_view_url", signed)

    res = await api_photos.order_photo_view_url("LK-1", "p1", principal=_principal())
    assert res["url"].startswith("https://signed.example/") and res["expires_in"] == 300


async def test_signed_view_url_service_is_scoped(monkeypatch):
    async def get_none(pid, fid):
        return None
    monkeypatch.setattr(order_photos_repo, "get", get_none)
    assert await svc.signed_view_url("p1", "fac-mine") is None  # not theirs → no URL

    async def get_row(pid, fid):
        return {"storage_key": "orders/AE/X/intake/a.jpg", "storage_provider": "r2"}
    async def fake_sign(*, object_key, provider=None, expires=None):
        return f"https://signed.example/{object_key}"
    monkeypatch.setattr(order_photos_repo, "get", get_row)
    monkeypatch.setattr(media_storage, "create_signed_view_url", fake_sign)
    out = await svc.signed_view_url("p1", "fac-mine")
    assert out["url"] == "https://signed.example/orders/AE/X/intake/a.jpg" and out["provider"] == "r2"
