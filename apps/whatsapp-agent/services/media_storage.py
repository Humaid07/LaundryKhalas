"""Generic media storage — Cloudflare R2 (S3-compatible) with a local fallback.

This is the ONE place that talks to object storage. Callers (e.g.
``services/order_photos``) hand it validated bytes + a PII-safe object key and
get back storage metadata; they never import boto3 or hold credentials
themselves. The dashboards never touch storage at all — they go through FastAPI.

Providers (``MEDIA_STORAGE_PROVIDER``):
  * ``local`` — dev/test fallback. Bytes are written to a gitignored folder
    (``apps/whatsapp-agent/storage/order-photos``, shared with the legacy photo
    store so existing local rows keep resolving). No credentials needed.
  * ``r2`` — Cloudflare R2, a PRIVATE S3-compatible bucket. Requires the full
    ``CLOUDFLARE_R2_*`` credential set; if any is missing this FAILS FAST (503)
    rather than silently falling back to local (never lose media silently).

Security posture (CLAUDE.md §7/§9): R2 bucket is private; the frontend never
receives credentials; view access is a SHORT-LIVED signed GET URL minted only
after the caller's permission check; type/size validators reject SVG/PDF/EXE and
anything off the allow-list (declared type must also match the file's magic
bytes). Object keys are caller-supplied and MUST be PII-safe (no name/phone/
address) — see ``services/order_photos._build_object_key``.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from settings import get_settings

# Local dev store — shared with the legacy order-photos folder so previously
# uploaded local rows keep resolving by their stored object key.
_LOCAL_ROOT = Path(__file__).resolve().parents[1] / "storage" / "order-photos"

# Supported raster image content-types → canonical file extension.
_IMAGE_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class MediaStorageError(Exception):
    """A storage/validation failure carrying the HTTP status the API should
    return (415 bad type, 413 too large, 422 empty, 503 provider unavailable)."""

    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------- validation --------------------------------
def sha256_hex(data: bytes) -> str:
    """Content hash for integrity / de-dupe / audit."""
    return hashlib.sha256(data).hexdigest()


def sniff_image_type(data: bytes) -> str | None:
    """Best-effort image type from MAGIC BYTES (not the client's claim). Returns
    a MIME string or None. Conservative: anything not positively one of our three
    raster formats is unknown (rejected), which blocks renamed exe / SVG."""
    if len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def guess_extension(content_type: str) -> str:
    return _IMAGE_EXT.get((content_type or "").split(";")[0].strip().lower(), "bin")


def validate_file_type(*, declared_type: str | None, data: bytes, allowed_types: set[str]) -> tuple[str, str]:
    """Validate an image upload → (content_type, ext), or raise MediaStorageError.
    Rejects types off ``allowed_types`` (415), empty files (422), and content whose
    magic bytes don't match the declared image type (415 — blocks SVG/PDF/EXE)."""
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared not in allowed_types:
        raise MediaStorageError(
            f"Unsupported file type '{declared or 'unknown'}'.", status_code=415
        )
    if not data:
        raise MediaStorageError("Empty file.", status_code=422)
    sniffed = sniff_image_type(data)
    if sniffed is None or sniffed != declared:
        raise MediaStorageError(
            "File content does not match a supported image format (JPG, PNG, WEBP).",
            status_code=415,
        )
    return declared, _IMAGE_EXT[declared]


def validate_file_size(data: bytes, max_bytes: int) -> None:
    """Raise MediaStorageError(413) if the payload exceeds the ceiling."""
    if len(data) > max_bytes:
        raise MediaStorageError("File exceeds the maximum allowed size.", status_code=413)


# ------------------------------ provider glue ------------------------------
def active_provider() -> str:
    """The configured media backend: 'r2' or (safe default) 'local'."""
    return get_settings().media_storage_provider_normalized


def bucket_name() -> str | None:
    s = get_settings()
    return (s.cloudflare_r2_bucket or None) if active_provider() == "r2" else None


_r2_client = None


def _r2():
    """Lazily build (and cache) the S3-compatible R2 client. Fails fast with a
    503 MediaStorageError when the provider is R2 but credentials are missing —
    the backend never silently degrades to local storage for a lost upload."""
    global _r2_client
    s = get_settings()
    if not s.r2_is_configured:
        raise MediaStorageError(
            "Cloudflare R2 is selected but not fully configured "
            "(missing CLOUDFLARE_R2_* credentials).",
            status_code=503,
        )
    if _r2_client is None:
        import boto3  # imported lazily so local-only dev needs no boto3 at import time
        from botocore.config import Config

        _r2_client = boto3.client(
            "s3",
            endpoint_url=s.cloudflare_r2_endpoint,
            aws_access_key_id=s.cloudflare_r2_access_key_id,
            aws_secret_access_key=s.cloudflare_r2_secret_access_key,
            region_name=s.cloudflare_r2_region or "auto",
            config=Config(signature_version="s3v4"),
        )
    return _r2_client


def reset_client_cache() -> None:
    """Drop the cached R2 client (tests override env between cases)."""
    global _r2_client
    _r2_client = None


async def upload_file(*, object_key: str, data: bytes, content_type: str, provider: str | None = None) -> dict:
    """Store bytes at ``object_key``. Returns
    ``{provider, bucket, object_key, public_url}``. R2 objects stay PRIVATE
    (public_url is None) — viewing goes through a signed URL."""
    provider = provider or active_provider()
    if provider == "r2":
        s = get_settings()
        client = _r2()
        await asyncio.to_thread(
            client.put_object,
            Bucket=s.cloudflare_r2_bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        return {"provider": "r2", "bucket": s.cloudflare_r2_bucket, "object_key": object_key, "public_url": None}
    dest = _LOCAL_ROOT / object_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(dest.write_bytes, data)
    return {"provider": "local", "bucket": None, "object_key": object_key, "public_url": None}


async def read_file(*, object_key: str, provider: str | None = None) -> bytes | None:
    """Read bytes back (for the Bearer-guarded content proxy). None if missing."""
    provider = provider or active_provider()
    if provider == "r2":
        s = get_settings()
        client = _r2()
        try:
            resp = await asyncio.to_thread(client.get_object, Bucket=s.cloudflare_r2_bucket, Key=object_key)
            return await asyncio.to_thread(resp["Body"].read)
        except Exception:
            return None
    path = _LOCAL_ROOT / object_key
    if not path.exists():
        return None
    return await asyncio.to_thread(path.read_bytes)


async def delete_file(*, object_key: str, provider: str | None = None) -> None:
    """Hard-delete the bytes. NOTE: order photos SOFT-delete (evidence is kept),
    so this is not called on the photo-delete path — it exists for the generic
    media API and future purge/retention jobs."""
    provider = provider or active_provider()
    if provider == "r2":
        s = get_settings()
        client = _r2()
        await asyncio.to_thread(client.delete_object, Bucket=s.cloudflare_r2_bucket, Key=object_key)
        return
    path = _LOCAL_ROOT / object_key
    if path.exists():
        await asyncio.to_thread(path.unlink)


async def create_signed_view_url(*, object_key: str, provider: str | None = None, expires: int | None = None) -> str | None:
    """A SHORT-LIVED signed GET URL for direct viewing from R2. Callers MUST have
    already run their permission check. Returns None for local storage (no object
    store to sign against — the client uses the Bearer content proxy instead)."""
    provider = provider or active_provider()
    s = get_settings()
    if provider == "r2":
        client = _r2()
        ttl = int(expires or s.media_signed_url_expires_seconds)
        return await asyncio.to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": s.cloudflare_r2_bucket, "Key": object_key},
            ExpiresIn=ttl,
        )
    return None


async def create_signed_upload_url(*, object_key: str, content_type: str, provider: str | None = None, expires: int | None = None) -> str | None:
    """A SHORT-LIVED signed PUT URL (reserved for future direct-to-R2 uploads).
    None for local. Not used by the current multipart-through-FastAPI flow."""
    provider = provider or active_provider()
    s = get_settings()
    if provider == "r2":
        client = _r2()
        ttl = int(expires or s.media_upload_signed_url_expires_seconds)
        return await asyncio.to_thread(
            client.generate_presigned_url,
            "put_object",
            Params={"Bucket": s.cloudflare_r2_bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=ttl,
        )
    return None
