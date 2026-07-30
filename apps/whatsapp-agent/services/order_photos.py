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

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from db.repositories import order_events_repo, order_photos_repo
from settings import get_settings

# storage/order-photos lives under apps/whatsapp-agent (parents[1] = that dir).
_STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "order-photos"

# stage → the order_events event_type recorded on upload.
_UPLOAD_EVENT = {
    "intake": "intake_photos_uploaded",
    "pre_dispatch": "pre_dispatch_photos_uploaded",
}

# content-type → file extension.
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


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


def _save_local(order_uuid: str, ext: str, data: bytes) -> tuple[str, str]:
    """Write bytes to the local dev store. Returns (storage_key, file_name)."""
    file_name = f"order-photo-{uuid4().hex}.{ext}"
    storage_key = f"{order_uuid}/{file_name}"
    dest = _STORAGE_ROOT / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return storage_key, file_name


async def add_photos(
    *,
    order_uuid: str,
    facility_id: str,
    stage: str,
    files: list[IncomingPhoto],
    actor_id: str | None = None,
    actor_name: str | None = None,
    is_test_data: bool = True,
) -> list[dict]:
    """Validate + store + persist a batch of photos for one order+stage, then
    write ONE order event. Validation is all-or-nothing: if any file is invalid
    nothing is stored. Returns the PII-safe photo views."""
    if stage not in order_photos_repo.STAGES:
        raise PhotoValidationError(
            f"Unknown stage '{stage}'. Use 'intake' or 'pre_dispatch'.", status_code=422)
    if not files:
        raise PhotoValidationError("No files were uploaded.", status_code=422)

    settings = get_settings()
    provider = settings.facility_order_photo_storage_normalized
    if provider != "local":
        # Cloud providers are reserved for a later task; never silently no-op.
        raise PhotoValidationError(
            f"Storage provider '{provider}' is not enabled yet.", status_code=503)

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
    for (content_type, ext), photo in validated:
        storage_key, file_name = _save_local(order_uuid, ext, photo.data)
        row = await order_photos_repo.create(
            order_uuid=order_uuid,
            facility_id=facility_id,
            stage=stage,
            storage_provider=provider,
            storage_key=storage_key,
            file_name=file_name,
            content_type=content_type,
            file_size=len(photo.data),
            uploaded_by_user_id=actor_id,
            uploaded_by_name=actor_name,
            metadata={"stage": stage},
            is_test_data=is_test_data,
        )
        if row:
            saved.append(order_photos_repo.to_read(row))

    # ONE audit event for the batch (PII-safe metadata only).
    await order_events_repo.create(
        order_uuid=order_uuid,
        event_type=_UPLOAD_EVENT[stage],
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


async def read_content(photo_id: str, facility_id: str) -> tuple[bytes, str, str] | None:
    """Return (bytes, content_type, file_name) for a facility's photo, or None if
    it isn't theirs / the file is missing. Reads from the local store."""
    row = await order_photos_repo.get(photo_id, facility_id)
    if not row:
        return None
    path = _STORAGE_ROOT / row["storage_key"]
    if not path.exists():
        return None
    return path.read_bytes(), row["content_type"], row["file_name"]


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
