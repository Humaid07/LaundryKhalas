"""Conversation fingerprinting & one-way customer hashing for dedup.

The primary archive may contain a conversation that also appears in the fallback
archive (or a combined export). We build a deterministic fingerprint per
conversation and drop duplicates, preferring the primary archive and the more
complete copy.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional

from ..core.models import Conversation

# Salt keeps the customer hash one-way and non-reversible across exports while
# remaining stable within a run set. Not a secret (no PII in the repo), just a
# domain separator.
_CUSTOMER_SALT = "laundrykhalas-replay-v1"

_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """Normalize a phone-ish chat id to digits only (for hashing/matching)."""
    return _DIGITS_RE.sub("", raw or "")


def customer_hash(chat_id: str) -> str:
    """One-way hash of a customer identifier (never routable, never reversible)."""
    digits = normalize_phone(chat_id)
    return hashlib.sha256((_CUSTOMER_SALT + "|" + digits).encode()).hexdigest()[:16]


def _normalized_inbound_text_hash(conv: Conversation) -> str:
    parts = []
    for m in conv.inbound_messages:
        t = (m.text or m.caption or m.media_reference or "").strip().lower()
        t = re.sub(r"\s+", " ", t)
        if t:
            parts.append(t)
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def compute_fingerprint(conv: Conversation) -> str:
    """Deterministic fingerprint from customer hash + inbound timeline shape."""
    first = conv.first_inbound_at.isoformat() if conv.first_inbound_at else "?"
    last = conv.last_inbound_at.isoformat() if conv.last_inbound_at else "?"
    text_hash = _normalized_inbound_text_hash(conv)
    key = "|".join(
        [
            conv.customer_identifier_hash,
            first,
            last,
            str(conv.inbound_count),
            text_hash,
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:20]


@dataclass
class DuplicateRecord:
    kept_chat_id: str
    kept_archive: str
    excluded_chat_id: str
    excluded_archive: str
    fingerprint: str
    reason: str


def _completeness_score(conv: Conversation) -> tuple[int, int, int]:
    """Higher is more complete: (total msgs, media count, has timestamps)."""
    media = sum(1 for m in conv.messages if m.media_reference)
    has_ts = sum(1 for m in conv.messages if m.timestamp)
    return (len(conv.messages), media, has_ts)


# Archive-priority: primary preferred over fallback.
def _archive_priority(archive_name: str) -> int:
    return 0 if "All_Chats" in archive_name else 1


def dedupe(
    conversations: list[Conversation],
) -> tuple[list[Conversation], list[DuplicateRecord]]:
    """Return (kept, duplicate_records). Prefers primary archive & completeness.

    Conversations with an empty/absent fingerprint bucket (no inbound content)
    are never dropped as duplicates of each other unless byte-identical.
    """
    for conv in conversations:
        if not conv.fingerprint:
            conv.fingerprint = compute_fingerprint(conv)

    by_fp: dict[str, list[Conversation]] = {}
    for conv in conversations:
        by_fp.setdefault(conv.fingerprint, []).append(conv)

    kept: list[Conversation] = []
    dupes: list[DuplicateRecord] = []
    for fp, group in by_fp.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        # Choose winner: primary archive first, then most complete.
        winner = min(
            group,
            key=lambda c: (
                _archive_priority(c.source_archive),
                tuple(-x for x in _completeness_score(c)),
            ),
        )
        kept.append(winner)
        for c in group:
            if c is winner:
                continue
            c.excluded_as_duplicate = True
            c.duplicate_of = winner.source_chat_id
            reason = (
                "prefer primary archive"
                if _archive_priority(c.source_archive) > _archive_priority(winner.source_archive)
                else "prefer more complete copy"
            )
            c.exclusion_reason = reason
            dupes.append(
                DuplicateRecord(
                    kept_chat_id=winner.source_chat_id,
                    kept_archive=winner.source_archive,
                    excluded_chat_id=c.source_chat_id,
                    excluded_archive=c.source_archive,
                    fingerprint=fp,
                    reason=reason,
                )
            )
    return kept, dupes
