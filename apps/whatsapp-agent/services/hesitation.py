"""Deterministic price-signal detection (spec §17).

Distinguishes a plain PRICE ENQUIRY ("how much?") — which must NOT trigger a
discount follow-up — from a real PRICE OBJECTION ("that's too expensive"). The
shadow classifier emits richer labels (PRICE_ENQUIRY / PRICE_PUSHBACK /
DISCOUNT_REQUEST), but its output is advisory; these pure helpers keep the
scheduling decision deterministic and testable. Objection detection wins when a
message carries both signals (e.g. "how much cheaper can you go"). Pure, no I/O.
"""
from __future__ import annotations

import re

_ENQUIRY = re.compile(
    r"\bhow much\b|\bwhat('?s| is| are)?\b.*\b(price|cost|rate|charge)\b|"
    r"\bprice (for|of)\b|\bcost (for|of)\b|\brate for\b",
    re.IGNORECASE,
)
_OBJECTION = re.compile(
    r"too expensive|too (much|costly)|that'?s a lot|\bpricey\b|over (my )?budget|"
    r"can you (make it )?cheaper|make it cheaper|\bcheaper\b|expensive|"
    r"that'?s expensive|bit much|come down (on|in)",
    re.IGNORECASE,
)


def is_price_objection(text: str) -> bool:
    return bool(_OBJECTION.search(text or ""))


def is_price_enquiry(text: str) -> bool:
    """A plain price question. An objection is never counted as a plain enquiry."""
    t = text or ""
    if is_price_objection(t):
        return False
    return bool(_ENQUIRY.search(t))
