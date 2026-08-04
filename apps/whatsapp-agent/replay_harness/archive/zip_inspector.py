"""Safe ZIP inspection & extraction for WhatsApp archives.

Security:
  - Rejects path traversal (absolute paths, `..` escaping the extract root).
  - Enforces limits: max single-file size, max total uncompressed size,
    max file count, max nested-archive depth.
  - Skips corrupt/malicious entries safely (logged, not fatal).

The harness works directly against the zip (no full extraction needed for HTML
parsing): it reads entries in-memory and enumerates media basenames so the
parser can flag missing binaries.
"""
from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterator, Optional

# Limits (generous but bounded — the primary archive is ~452MB compressed).
MAX_FILE_SIZE = 200 * 1024 * 1024          # 200 MB per entry
MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024    # 4 GB total uncompressed
MAX_FILE_COUNT = 20000
MAX_NESTED_DEPTH = 2

_CONVERSATION_EXT = (".html", ".htm", ".txt", ".json", ".csv")
_MEDIA_EXT = (
    ".jpeg", ".jpg", ".png", ".webp", ".gif",
    ".oga", ".ogg", ".mp3", ".m4a", ".opus", ".aac", ".wav",
    ".mp4", ".3gp", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".vcf",
)
# Web-export scaffolding that is NOT a conversation.
_ASSET_PREFIXES = ("css/", "js/", "imgs/emoji/", "css/emoji/")


@dataclass
class ArchiveEntry:
    path: str
    file_type: str          # extension without dot, or 'dir'
    size: int
    is_conversation_candidate: bool = False
    is_media: bool = False
    is_asset: bool = False
    parse_status: str = "pending"   # pending|parsed|skipped|error
    note: str = ""


@dataclass
class ArchiveInventory:
    archive_path: str
    entries: list[ArchiveEntry] = field(default_factory=list)
    skipped_unsafe: list[str] = field(default_factory=list)
    total_uncompressed: int = 0
    nested_archives: list[str] = field(default_factory=list)

    @property
    def conversation_candidates(self) -> list[ArchiveEntry]:
        return [e for e in self.entries if e.is_conversation_candidate]

    @property
    def media_entries(self) -> list[ArchiveEntry]:
        return [e for e in self.entries if e.is_media]

    def media_basenames(self) -> set[str]:
        return {e.path.rsplit("/", 1)[-1] for e in self.media_entries}


def _is_safe_member(name: str) -> bool:
    """Reject path traversal / absolute members."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    if os.path.isabs(name):
        return False
    p = PurePosixPath(name.replace("\\", "/"))
    if any(part == ".." for part in p.parts):
        return False
    # Drive-letter style (Windows) e.g. "C:foo"
    if len(name) >= 2 and name[1] == ":":
        return False
    return True


def _classify(name: str, size: int) -> ArchiveEntry:
    lower = name.lower()
    ext = Path(name).suffix.lower()
    is_asset = any(lower.startswith(p) for p in _ASSET_PREFIXES)
    is_conv = (not is_asset) and ext in _CONVERSATION_EXT and size > 0
    is_media = (not is_asset) and ext in _MEDIA_EXT
    return ArchiveEntry(
        path=name,
        file_type=(ext[1:] if ext else "noext"),
        size=size,
        is_conversation_candidate=is_conv,
        is_media=is_media,
        is_asset=is_asset,
    )


def inspect_archive(archive_path: str, *, depth: int = 0) -> ArchiveInventory:
    """Enumerate an archive's contents into an inventory with safety checks."""
    inv = ArchiveInventory(archive_path=archive_path)
    try:
        zf = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError) as exc:
        inv.skipped_unsafe.append(f"{archive_path}: cannot open ({exc})")
        return inv

    with zf:
        count = 0
        for info in zf.infolist():
            name = info.filename
            if info.is_dir():
                continue
            count += 1
            if count > MAX_FILE_COUNT:
                inv.skipped_unsafe.append("MAX_FILE_COUNT exceeded; remaining entries skipped")
                break
            if not _is_safe_member(name):
                inv.skipped_unsafe.append(f"unsafe path: {name}")
                continue
            if info.file_size > MAX_FILE_SIZE:
                inv.skipped_unsafe.append(f"oversize entry ({info.file_size}B): {name}")
                continue
            inv.total_uncompressed += info.file_size
            if inv.total_uncompressed > MAX_TOTAL_SIZE:
                inv.skipped_unsafe.append("MAX_TOTAL_SIZE exceeded; remaining entries skipped")
                break
            entry = _classify(name, info.file_size)
            if entry.file_type == "zip":
                inv.nested_archives.append(name)
                if depth >= MAX_NESTED_DEPTH:
                    entry.note = "nested archive depth limit; not recursed"
            inv.entries.append(entry)
    return inv


def read_member(archive_path: str, member: str) -> Optional[bytes]:
    """Safely read one member's bytes, or None on error."""
    if not _is_safe_member(member):
        return None
    try:
        with zipfile.ZipFile(archive_path) as zf:
            info = zf.getinfo(member)
            if info.file_size > MAX_FILE_SIZE:
                return None
            return zf.read(member)
    except (KeyError, zipfile.BadZipFile, OSError):
        return None


def iter_conversation_members(inv: ArchiveInventory) -> Iterator[ArchiveEntry]:
    """Yield conversation-candidate entries (HTML/TXT/JSON/CSV)."""
    for e in inv.conversation_candidates:
        yield e
