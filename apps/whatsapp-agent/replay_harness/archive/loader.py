"""Load conversations from the primary (and optionally fallback) archive.

Pipeline: inspect -> parse each conversation candidate -> fingerprint ->
categorize -> dedupe (prefer primary). Returns kept conversations plus artifacts
for the inventory/parsing/duplicate reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..core.models import Conversation, Direction
from . import zip_inspector as zi
from .categorize import categorize
from .fingerprint import DuplicateRecord, compute_fingerprint, customer_hash, dedupe
from .html_parser import parse_html, resolve_media_availability


@dataclass
class LoadResult:
    conversations: list[Conversation]
    duplicates: list[DuplicateRecord]
    inventories: list[zi.ArchiveInventory] = field(default_factory=list)
    parse_errors: list[dict] = field(default_factory=list)
    primary_path: Optional[str] = None
    fallback_path: Optional[str] = None
    used_fallback_for: list[str] = field(default_factory=list)

    @property
    def kept(self) -> list[Conversation]:
        return [c for c in self.conversations if not c.excluded_as_duplicate]

    @property
    def replayable(self) -> list[Conversation]:
        return [c for c in self.kept if c.inbound_count > 0]


def _chat_id_from_path(member_path: str) -> str:
    # "+44 7519 510517/+44 7519 510517.html" -> "+44 7519 510517"
    folder = member_path.rsplit("/", 1)[0] if "/" in member_path else member_path
    return Path(folder).name or Path(member_path).stem


def _parse_one(
    archive_path: str,
    archive_name: str,
    entry: zi.ArchiveEntry,
    media_basenames: set[str],
    parse_errors: list[dict],
) -> Optional[Conversation]:
    if entry.file_type not in ("html", "htm"):
        # Only HTML is present in these archives; other formats are logged as
        # unsupported for now (extend here for TXT/JSON exports).
        parse_errors.append(
            {"archive": archive_name, "path": entry.path, "error": f"unsupported format .{entry.file_type}"}
        )
        entry.parse_status = "skipped"
        return None
    raw = zi.read_member(archive_path, entry.path)
    if raw is None:
        parse_errors.append({"archive": archive_name, "path": entry.path, "error": "unreadable member"})
        entry.parse_status = "error"
        return None
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", "replace")
    chat_id = _chat_id_from_path(entry.path)
    chash = customer_hash(chat_id)
    try:
        messages = parse_html(
            content,
            source_chat_id=chat_id,
            source_filename=entry.path,
            sender_identifier_hash=chash,
        )
    except Exception as exc:  # noqa: BLE001 - parsing must never crash the run
        parse_errors.append({"archive": archive_name, "path": entry.path, "error": f"parse: {exc}"})
        entry.parse_status = "error"
        return None
    resolve_media_availability(messages, available_basenames=media_basenames)
    conv = Conversation(
        source_archive=archive_name,
        source_chat_id=chat_id,
        source_filename=entry.path,
        customer_identifier_hash=chash,
        messages=messages,
    )
    conv.fingerprint = compute_fingerprint(conv)
    conv.category = categorize(conv)
    entry.parse_status = "parsed"
    return conv


def load_archives(
    primary_path: Optional[str],
    fallback_path: Optional[str] = None,
) -> LoadResult:
    """Load & dedupe conversations from primary (+ fallback) archives."""
    if not primary_path:
        raise FileNotFoundError(
            "Primary archive not found. Set WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH "
            "or place WhatsApp_All_Chats.zip in a searched directory."
        )

    result = LoadResult(conversations=[], duplicates=[], primary_path=primary_path,
                        fallback_path=fallback_path)

    # --- primary ---
    primary_name = Path(primary_path).name
    inv_primary = zi.inspect_archive(primary_path)
    result.inventories.append(inv_primary)
    media_primary = inv_primary.media_basenames()
    primary_convs: list[Conversation] = []
    primary_chat_ids: set[str] = set()
    for entry in inv_primary.conversation_candidates:
        conv = _parse_one(primary_path, primary_name, entry, media_primary, result.parse_errors)
        if conv is not None:
            primary_convs.append(conv)
            primary_chat_ids.add(conv.source_chat_id)

    all_convs = list(primary_convs)

    # --- fallback (only fills gaps: chat ids absent from primary) ---
    if fallback_path and Path(fallback_path).is_file():
        fb_name = Path(fallback_path).name
        inv_fb = zi.inspect_archive(fallback_path)
        result.inventories.append(inv_fb)
        media_fb = inv_fb.media_basenames()
        for entry in inv_fb.conversation_candidates:
            chat_id = _chat_id_from_path(entry.path)
            if chat_id in primary_chat_ids:
                # Present in primary already; skip (primary is authoritative).
                entry.parse_status = "skipped"
                entry.note = "present in primary archive"
                continue
            conv = _parse_one(fallback_path, fb_name, entry, media_fb, result.parse_errors)
            if conv is not None and conv.inbound_count > 0:
                all_convs.append(conv)
                result.used_fallback_for.append(conv.source_chat_id)

    kept, dupes = dedupe(all_convs)
    result.conversations = all_convs  # includes ones flagged excluded_as_duplicate
    result.duplicates = dupes
    return result
