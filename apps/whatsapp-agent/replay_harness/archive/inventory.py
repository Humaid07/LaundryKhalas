"""Archive inventory & parsing report writers (no LLM).

Produces:
  - archive_inventory.csv       (one row per archive entry)
  - archive_parsing_report.json (summary of what parsed / was skipped)
  - duplicate_conversations.csv (excluded duplicates + reasons)
  - unsupported_messages.csv    (system/media/empty/unsupported messages)
  - media_mapping_report.csv    (media refs -> availability)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from ..core.models import Conversation, Direction, MessageType
from .loader import LoadResult


def write_inventory_csv(result: LoadResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "archive", "path", "file_type", "size_bytes", "conversation_candidate",
            "is_media", "is_asset", "parse_status", "note",
        ])
        for inv in result.inventories:
            archive_name = Path(inv.archive_path).name
            for e in inv.entries:
                w.writerow([
                    archive_name, e.path, e.file_type, e.size,
                    e.is_conversation_candidate, e.is_media, e.is_asset,
                    e.parse_status, e.note,
                ])


def write_parsing_report_json(result: LoadResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    inv_summaries = []
    for inv in result.inventories:
        inv_summaries.append({
            "archive": Path(inv.archive_path).name,
            "path": inv.archive_path,
            "total_entries": len(inv.entries),
            "conversation_candidates": len(inv.conversation_candidates),
            "media_entries": len(inv.media_entries),
            "total_uncompressed_bytes": inv.total_uncompressed,
            "nested_archives": inv.nested_archives,
            "skipped_unsafe": inv.skipped_unsafe,
        })
    kept = result.kept
    replayable = result.replayable
    report = {
        "primary_path": result.primary_path,
        "fallback_path": result.fallback_path,
        "archives": inv_summaries,
        "conversations_parsed": len(result.conversations),
        "conversations_kept": len(kept),
        "conversations_replayable": len(replayable),
        "duplicates_excluded": len(result.duplicates),
        "used_fallback_for": result.used_fallback_for,
        "parse_errors": result.parse_errors,
        "total_inbound_messages": sum(c.inbound_count for c in replayable),
        "total_outbound_messages": sum(len(c.outbound_messages) for c in replayable),
        "categories": _category_counts(replayable),
    }
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def _category_counts(convs: Iterable[Conversation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in convs:
        counts[c.category] = counts.get(c.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def write_duplicates_csv(result: LoadResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "kept_chat_id", "kept_archive", "excluded_chat_id",
            "excluded_archive", "fingerprint", "reason",
        ])
        for d in result.duplicates:
            w.writerow([
                d.kept_chat_id, d.kept_archive, d.excluded_chat_id,
                d.excluded_archive, d.fingerprint, d.reason,
            ])


def write_unsupported_csv(result: LoadResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    non_replay = (Direction.SYSTEM_EVENT, Direction.UNSUPPORTED_MESSAGE, Direction.EMPTY_MESSAGE)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chat_id", "message_id", "direction", "message_type", "text_preview"])
        for conv in result.kept:
            for m in conv.messages:
                if m.direction in non_replay:
                    w.writerow([
                        conv.source_chat_id, m.source_message_id, m.direction.value,
                        m.message_type.value, (m.text or "")[:80],
                    ])


def write_media_mapping_csv(result: LoadResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "chat_id", "message_id", "direction", "media_type",
            "media_reference", "binary_available",
        ])
        for conv in result.kept:
            for m in conv.messages:
                if m.media_reference:
                    w.writerow([
                        conv.source_chat_id, m.source_message_id, m.direction.value,
                        m.message_type.value, m.media_reference, m.media_available,
                    ])


def write_all(result: LoadResult, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "archive_inventory.csv": out_dir / "archive_inventory.csv",
        "archive_parsing_report.json": out_dir / "archive_parsing_report.json",
        "duplicate_conversations.csv": out_dir / "duplicate_conversations.csv",
        "unsupported_messages.csv": out_dir / "unsupported_messages.csv",
        "media_mapping_report.csv": out_dir / "media_mapping_report.csv",
    }
    write_inventory_csv(result, paths["archive_inventory.csv"])
    write_parsing_report_json(result, paths["archive_parsing_report.json"])
    write_duplicates_csv(result, paths["duplicate_conversations.csv"])
    write_unsupported_csv(result, paths["unsupported_messages.csv"])
    write_media_mapping_csv(result, paths["media_mapping_report.csv"])
    return {k: str(v) for k, v in paths.items()}
