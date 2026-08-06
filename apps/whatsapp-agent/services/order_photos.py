"""Facility order-photo service: validation, storage, and audit.

Mock-first (CLAUDE.md §5): the default storage backend is ``local`` — bytes are
written to a gitignored dev folder and served back through the facility-scoped
content endpoint. No cloud credentials are required or referenced here; the
"supabase"/"r2" providers are reserved for a later live task.

Security posture:
  * Only raster image types on the allow-list (JPG/PNG/WEBP). The DECLARED
    content-type must also match the file's MAGIC BYTES, so a renamed
    executable or an SVG (text/`<`) is rejected even with an image content-type.
  * A per-image size ceiling and a per-order-stage count ceiling.
  * File names are GENERATED (``order-photo-<uuid>.<ext>``) — the client's
    original filename is never persisted, so no customer PII can leak via names.
  * Storage keys are generated from UUIDs (never a client string), so there is
    no path-traversal surface.

Every successful upload writes ONE ``order_events`` row
(``intake_photos_uploaded`` / ``pre_dispatch_photos_uploaded``); a delete writes
``order_photo_deleted``. Metadata is PII-safe (stage, count, uploader label).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from db.repositories import order_events_repo, order_photos_repo
from services import media_storage
from settings import get_settings

# stage → the order_events event_type recorded on upload.
_UPLOAD_EVENT = {
    "intake": "intake_photos_uploaded",
    "pre_dispatch": "pre_dispatch_photos_uploaded",
}

# stage → the facility-facing photo SOURCE when the uploader doesn't specify one.
_STAGE_SOURCE = {
    "intake": "FACILITY_BEFORE_PROCESSING",
    "pre_dispatch": "FACILITY_AFTER_PROCESSING",
    "issue_photo": "FACILITY_ISSUE",
    "damage_report": "INSPECTION",
}

# Stages the facility may upload to (DB CHECK also enforces this vocabulary).
# intake/pre_dispatch are the proof stages; issue_photo/damage_report back the
# Raise-an-Issue + inspection flows.
_UPLOAD_STAGES = frozenset({"intake", "pre_dispatch", "issue_photo", "damage_report"})

# content-type → file extension.
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _slug(value: str | None) -> str:
    """Path-safe token for an object key: uppercase, keep [A-Z0-9-], drop the
    rest. Used only for the market code + order reference (never customer data)."""
    return re.sub(r"[^A-Z0-9-]+", "", (value or "").upper().replace(" ", "-")).strip("-")


def _build_object_key(*, market_code: str | None, order_ref: str | None, order_uuid: str, stage: str, ext: str) -> str:
    """PII-SAFE object key: ``orders/{market}/{order_ref}/{stage}/{uuid}.{ext}``.
    No customer name / phone / address / facility / driver name. Falls back to the
    order UUID (also non-PII) when a market/reference isn't supplied."""
    market = _slug(market_code) or "XX"
    ref = _slug(order_ref) or _slug(order_uuid) or "ORDER"
    return f"orders/{market}/{ref}/{stage}/{uuid4().hex}.{ext}"


class PhotoValidationError(Exception):
    """A rejected upload (bad type / too large / stage full / bad stage). Carries
    the HTTP status the API should return."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class IncomingPhoto:
    """One file read off the multipart request (bytes already in memory)."""
    filename: str | None
    content_type: str | None
    data: bytes


def _sniff_type(data: bytes) -> str | None:
    """Best-effort image type from magic bytes. Returns a MIME string or None.
    Deliberately conservative — anything it can't positively identify as one of
    our three raster formats is treated as unknown (and thus rejected)."""
    if len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_one(photo: IncomingPhoto) -> tuple[str, str]:
    """Validate a single file → (content_type, ext), or raise PhotoValidationError."""
    settings = get_settings()
    allowed = settings.facility_order_photo_allowed_types_set
    max_bytes = settings.facility_order_photo_max_bytes

    declared = (photo.content_type or "").split(";")[0].strip().lower()
    if declared not in allowed:
        raise PhotoValidationError(
            f"Unsupported file type '{declared or 'unknown'}'. Allowed: JPG, PNG, WEBP.",
            status_code=415,
        )
    if not photo.data:
        raise PhotoValidationError("Empty file.", status_code=422)
    if len(photo.data) > max_bytes:
        raise PhotoValidationError(
            f"File is larger than the {settings.facility_order_photo_max_mb}MB limit.",
            status_code=413,
        )
    sniffed = _sniff_type(photo.data)
    # The real bytes must be one of our raster formats AND match the declared type
    # — blocks a renamed executable/SVG smuggled behind an image content-type.
    if sniffed is None or sniffed != declared:
        raise PhotoValidationError(
            "File content does not match a supported image format (JPG, PNG, WEBP).",
            status_code=415,
        )
    return declared, _EXT[declared]


async def add_photos(
    *,
    order_uuid: str,
    facility_id: str,
    stage: str,
    files: list[IncomingPhoto],
    market_code: str | None = None,
    order_ref: str | None = None,
    actor_id: str | None = None,
    actor_name: str | None = None,
    order_item_id: str | None = None,
    caption: str | None = None,
    source: str | None = None,
    is_test_data: bool = True,
) -> list[dict]:
    """Validate + store (local or Cloudflare R2) + persist a batch of photos for
    one order+stage, then write ONE order event. Validation is all-or-nothing: if
    any file is invalid nothing is stored. Returns the PII-safe photo views.

    ``order_item_id`` optionally links the batch to a specific line item; ``source``
    is the facility-facing provenance (defaults from the stage).

    Files go to the configured MEDIA_STORAGE_PROVIDER via ``media_storage``; when
    provider=r2 but credentials are missing the storage layer raises 503 (never a
    silent local fallback for a lost upload)."""
    if stage not in _UPLOAD_STAGES:
        raise PhotoValidationError(
            f"Unknown stage '{stage}'. Allowed: {', '.join(sorted(_UPLOAD_STAGES))}.",
            status_code=422)
    if not files:
        raise PhotoValidationError("No files were uploaded.", status_code=422)

    settings = get_settings()

    # Validate ALL first (all-or-nothing) so a bad file never leaves a partial batch.
    validated = [(_validate_one(f), f) for f in files]

    # Per-stage cap over the LIVE (non-deleted) count.
    max_per_stage = settings.facility_order_photo_max_per_stage
    existing = await order_photos_repo.count_for_stage(order_uuid, stage)
    if existing + len(files) > max_per_stage:
        remaining = max(0, max_per_stage - existing)
        raise PhotoValidationError(
            f"This stage allows up to {max_per_stage} photos "
            f"({existing} already uploaded, {remaining} more allowed).",
            status_code=409,
        )

    saved: list[dict] = []
    try:
        for (content_type, ext), photo in validated:
            object_key = _build_object_key(
                market_code=market_code, order_ref=order_ref,
                order_uuid=order_uuid, stage=stage, ext=ext,
            )
            stored = await media_storage.upload_file(
                object_key=object_key, data=photo.data, content_type=content_type,
            )
            # Display/download name stays a GENERATED safe name (the client's
            # original filename is never persisted — it can carry customer PII).
            file_name = f"order-photo-{uuid4().hex}.{ext}"
            row = await order_photos_repo.create(
                order_uuid=order_uuid,
                facility_id=facility_id,
                stage=stage,
                order_item_id=order_item_id,
                caption=caption,
                source=source or _STAGE_SOURCE.get(stage),
                storage_provider=stored["provider"],
                storage_key=stored["object_key"],
                bucket=stored.get("bucket"),
                public_url=stored.get("public_url"),
                file_name=file_name,
                content_type=content_type,
                file_size=len(photo.data),
                checksum_sha256=media_storage.sha256_hex(photo.data),
                source_channel="facility_dashboard",
                visibility_scope="facility",
                status="active",
                uploaded_by_user_id=actor_id,
                uploaded_by_name=actor_name,
                metadata={"stage": stage},
                is_test_data=is_test_data,
            )
            if row:
                saved.append(order_photos_repo.to_read(row))
    except media_storage.MediaStorageError as exc:
        # Surface storage failures (e.g. R2 unconfigured/unavailable) with a
        # proper HTTP status; nothing partial is exposed to the caller.
        raise PhotoValidationError(str(exc), status_code=exc.status_code)

    # ONE audit event for the batch (PII-safe metadata only).
    await order_events_repo.create(
        order_uuid=order_uuid,
        event_type=_UPLOAD_EVENT.get(stage, "order_photos_uploaded"),
        actor_type="facility",
        actor_name=actor_name or "Facility",
        notes=f"{len(saved)} {stage.replace('_', '-')} photo(s) uploaded.",
        metadata={
            "photo_count": len(saved),
            "stage": stage,
            "uploaded_by": actor_name,
            "facility_id": facility_id,
        },
        is_test_data=is_test_data,
    )
    return saved


async def list_photos(order_uuid: str, *, stage: str | None = None) -> list[dict]:
    rows = await order_photos_repo.list_for_order(order_uuid, stage=stage)
    return [order_photos_repo.to_read(r) for r in rows]


async def link_photo_to_item(
    photo_id: str,
    facility_id: str,
    *,
    order_item_id: str | None,
    caption: str | None = None,
    actor_name: str | None = None,
) -> dict | None:
    """Link (or unlink with order_item_id=None) a facility's photo to a line item.
    Returns the PII-safe view + writes an audit event, or None if the photo isn't
    this facility's live photo."""
    row = await order_photos_repo.set_item_link(
        photo_id, facility_id, order_item_id=order_item_id, caption=caption)
    if not row:
        return None
    await order_events_repo.create(
        order_uuid=str(row["order_id"]),
        event_type="order_photo_relinked",
        actor_type="facility",
        actor_name=actor_name or "Facility",
        notes=("Photo linked to an item." if order_item_id else "Photo unlinked from its item."),
        metadata={"photo_id": str(row["id"]), "order_item_id": order_item_id, "facility_id": facility_id},
    )
    return order_photos_repo.to_read(row)


async def read_content(photo_id: str, facility_id: str) -> tuple[bytes, str, str] | None:
    """Return (bytes, content_type, file_name) for a facility's photo, or None if
    it isn't theirs / the file is missing. Reads from the row's provider (local
    disk or R2) via the storage layer."""
    row = await order_photos_repo.get(photo_id, facility_id)
    if not row:
        return None
    data = await media_storage.read_file(
        object_key=row["storage_key"], provider=row.get("storage_provider"))
    if data is None:
        return None
    return data, row["content_type"], row["file_name"]


async def read_content_by_id(
    photo_id: str, *, order_uuid: str | None = None
) -> tuple[bytes, str, str] | None:
    """Return (bytes, content_type, file_name) for a photo by id — NOT facility
    scoped (for the internal ops/admin read-only view). When ``order_uuid`` is
    given, the photo must belong to that order (defence against id-mixing).
    Callers must already be ops-authorized."""
    row = await order_photos_repo.get_any(photo_id)
    if not row:
        return None
    if order_uuid and str(row["order_id"]) != str(order_uuid):
        return None
    data = await media_storage.read_file(
        object_key=row["storage_key"], provider=row.get("storage_provider"))
    if data is None:
        return None
    return data, row["content_type"], row["file_name"]


async def signed_view_url(photo_id: str, facility_id: str) -> dict | None:
    """A short-lived signed GET URL for a facility's photo — minted ONLY after the
    facility-scoped ownership check. Returns ``{"url", "expires_in"}`` for R2, or
    ``{"url": None, ...}`` for local storage (the client then uses the Bearer
    content proxy). None when the photo isn't this facility's live photo."""
    row = await order_photos_repo.get(photo_id, facility_id)
    if not row:
        return None
    expires = get_settings().media_signed_url_expires_seconds
    url = await media_storage.create_signed_view_url(
        object_key=row["storage_key"], provider=row.get("storage_provider"), expires=expires)
    return {"url": url, "expires_in": int(expires), "provider": row.get("storage_provider")}


async def delete_photo(
    photo_id: str, facility_id: str, *, actor_name: str | None = None
) -> dict | None:
    """Soft-delete a facility's photo (bytes are retained as evidence) + audit.
    Returns the PII-safe view, or None if it wasn't the facility's live photo."""
    row = await order_photos_repo.soft_delete(photo_id, facility_id)
    if not row:
        return None
    await order_events_repo.create(
        order_uuid=str(row["order_id"]),
        event_type="order_photo_deleted",
        actor_type="facility",
        actor_name=actor_name or "Facility",
        notes=f"A {row['stage'].replace('_', '-')} photo was removed.",
        metadata={"stage": row["stage"], "removed_by": actor_name, "facility_id": facility_id},
    )
    return order_photos_repo.to_read(row)
