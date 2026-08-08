"""Split a model reply into 1-3 validated WhatsApp messages (spec §3 / §20).

The model may separate intended messages with a line containing only the
delimiter (three dashes). The backend is authoritative: it trims segments,
drops empty / one-word fragments, dedups adjacent duplicates, refuses
mid-sentence splits (merging them back), and caps the count by merging any
overflow into the last kept segment. A reply with no delimiter is a single
message. This module is pure (no I/O) and never raises.
"""
from __future__ import annotations

import re

_SENTENCE_END = (".", "?", "!", ":", "…", "؟")  # incl. Arabic question mark


def _is_fragment(seg: str) -> bool:
    """A segment too small to stand alone as its own WhatsApp message."""
    s = seg.strip()
    return not s or len(s.split()) < 2


def _looks_midsentence(prev: str, nxt: str) -> bool:
    """True when `nxt` reads as a continuation of `prev` (a bad split point)."""
    if not prev or not nxt:
        return False
    prev_ok = prev.rstrip().endswith(_SENTENCE_END)
    starts_lower = nxt.lstrip()[:1].islower()
    return (not prev_ok) or starts_lower


def finalize_reply(
    text: str, recent_agent_texts: list[str] | None = None, *, max_segments: int = 3
) -> list[str]:
    """Turn one model reply into the ordered messages to actually send.

    Applies the no-CTA guard (§16) — if the agent used a booking CTA in a recent
    message, a trailing bare CTA is stripped so it doesn't repeat — then segments
    into 1..max_segments validated messages (§3/§20). Operational questions are
    never stripped; the text is never emptied.
    """
    from services import conversion_guard

    out = text or ""
    if conversion_guard.recent_cta_count(recent_agent_texts or []) >= 1:
        out = conversion_guard.strip_trailing_cta(out)
    return segment_reply(out, max_segments=max_segments)


def segment_reply(text: str, *, max_segments: int = 3, delimiter: str = "---") -> list[str]:
    """Return 1..max_segments validated WhatsApp messages from a model reply."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(rf"(?m)^[ \t]*{re.escape(delimiter)}[ \t]*$", raw)
    segs: list[str] = []
    for part in parts:
        s = part.strip()
        if not s or _is_fragment(s):
            continue  # empty or one-word fragment -> drop (spec: no one-word fragments)
        # A mid-sentence continuation folds back into the previous segment rather
        # than becoming its own message.
        if segs and _looks_midsentence(segs[-1], s):
            segs[-1] = f"{segs[-1]} {s}".strip()
            continue
        if segs and segs[-1] == s:
            continue  # dedup adjacent identical
        segs.append(s)
    if not segs:
        return [raw]
    # Cap: merge overflow into the last kept segment so nothing is lost.
    while len(segs) > max_segments:
        tail = segs.pop()
        segs[-1] = f"{segs[-1]} {tail}".strip()
    return segs
