"""Detect and suppress unnecessary conversion CTAs (spec §4 / §16).

An unnecessary CTA is a booking / sales question ("would you like to book?")
appended to an answer. Operational questions that are genuinely required for the
next step (address, location pin, slot choice, explicit price / quote approval,
service clarification) are NOT CTAs and are never stripped. Pure, no I/O.
"""
from __future__ import annotations

import re

# Sales / booking nudges. Kept specific to avoid false positives.
_CTA_PATTERNS = [
    r"would you like (me |us )?to (proceed|book|arrange|go ahead|order|collect)",
    r"would you like to (proceed|book|order|go ahead)",
    r"would you still like to (proceed|book|go ahead)",
    r"shall i (book|arrange|order|go ahead)",
    r"do you want (me |us )?to (proceed|book|go ahead|arrange)",
    r"ready to book",
    r"want to (book|proceed|go ahead)\s*\??$",
]
# Required next-step questions that can look like a CTA but must be preserved.
_OPERATIONAL_PATTERNS = [
    r"shall i proceed with the work",   # revised-price approval (§22)
    r"final price is",
    r"which (slot|one|time)",
    r"please (send|share)",
    r"cleaning only or",                # service clarification
    r"is it .* or .*\?",
]
_CTA_RE = re.compile("|".join(_CTA_PATTERNS), re.IGNORECASE)
_OP_RE = re.compile("|".join(_OPERATIONAL_PATTERNS), re.IGNORECASE)


def is_conversion_cta(text: str) -> bool:
    """True when `text` is an unnecessary booking/conversion nudge (not operational)."""
    t = (text or "").strip()
    if not t or _OP_RE.search(t):
        return False
    return bool(_CTA_RE.search(t))


def recent_cta_count(agent_texts: list[str]) -> int:
    """How many of the recent agent messages ended in an unnecessary CTA."""
    return sum(1 for t in (agent_texts or []) if is_conversion_cta(t))


def strip_trailing_cta(text: str) -> str:
    """Drop a trailing sentence that is a bare conversion CTA. If the whole text is
    a CTA (nothing else to keep), return it unchanged — stripping would empty it."""
    t = (text or "").strip()
    if not t:
        return t
    sentences = re.split(r"(?<=[.?!])\s+", t)
    kept = list(sentences)
    while kept and is_conversion_cta(kept[-1]):
        kept.pop()
    return " ".join(kept).strip() or t
