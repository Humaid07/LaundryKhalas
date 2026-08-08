"""PII sanitiser for building evaluation/tuning data from historical chats.

Raw six-month WhatsApp data must NEVER be used directly as an unrestricted prompt
corpus (spec). Before any example is stored for evaluation or tuning it is passed
through here to remove/mask phone numbers, emails, full addresses, payment/media
URLs, order IDs, long digit runs (accounts/cards), and — optionally — names. Pure
and deterministic so the same input always yields the same redaction.
"""
from __future__ import annotations

import re

# Order-of-application matters: emails/URLs before bare digit runs so we don't
# shred an email's domain or a URL's port first.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://\S+|www\.\S+")
_ORDER_ID = re.compile(r"\bLK-[A-Z0-9]{2,}-?\d{2,}\b", re.IGNORECASE)
# Phone: +country and/or 7+ digit runs allowing spaces/dashes/parens.
_PHONE = re.compile(r"(?:(?:\+|00)\d[\d\s().\-]{6,}\d)")
_LONG_DIGITS = re.compile(r"\b\d[\d\s\-]{6,}\d\b")
# A very rough "Villa/Flat/Apt/Building + number" full-address hint.
_ADDRESS = re.compile(
    r"\b(?:villa|flat|apt|apartment|building|bldg|street|str|st|floor)\b[\w\s,#.\-]{0,40}\d+",
    re.IGNORECASE,
)
_API_KEY = re.compile(r"\b(?:sk-ant-[A-Za-z0-9_\-]{6,}|sk-[A-Za-z0-9]{10,}|AKIA[A-Z0-9]{10,})\b")


def sanitize_text(text: str | None, *, mask_names: bool = False,
                  names: list[str] | None = None) -> str:
    """Redact PII from free text. ``names`` (when given with mask_names) masks
    those specific tokens; general name detection is intentionally NOT attempted
    (too lossy) — pass known names explicitly instead."""
    if not text:
        return ""
    s = str(text)
    s = _API_KEY.sub("[REDACTED_KEY]", s)
    s = _EMAIL.sub("[EMAIL]", s)
    s = _URL.sub("[URL]", s)
    s = _ORDER_ID.sub("[ORDER_ID]", s)
    s = _ADDRESS.sub("[ADDRESS]", s)
    s = _PHONE.sub("[PHONE]", s)
    s = _LONG_DIGITS.sub("[NUMBER]", s)
    if mask_names and names:
        for n in names:
            if n and len(n) >= 2:
                s = re.sub(rf"\b{re.escape(n)}\b", "[NAME]", s, flags=re.IGNORECASE)
    return s


# --- Conversational name scrubbing (targeted, low-lossy) --------------------
# General name detection is too lossy to attempt (see sanitize_text). But names
# volunteered right after an introduction phrase ("I'm Ahmed", "this is Sara",
# "my name is ...") are both high-signal PII and easy to catch precisely. We mask
# ONLY the capitalised token(s) following such a phrase, skipping common words that
# are not names, so retrieval quality is preserved. Used when redacting real chats
# for the retrieval KB (scripts/index_chat_kb.py).
_INTRO_NAME = re.compile(
    r"(?P<lead>(?i:\b(?:i['’]?m|i\s+am|this\s+is|my\s+name\s+is|myself|name\s+is|i\s+am\s+called|call\s+me))\s+)"
    r"(?P<name>[A-Z][a-z]{1,19}(?:\s+[A-Z][a-z]{1,19})?)"
)
# Capitalised words that follow an intro phrase but are NOT names.
_NOT_A_NAME = frozenset({
    "ok", "okay", "yes", "no", "yeah", "here", "there", "fine", "good", "great",
    "sorry", "thanks", "thank", "sir", "madam", "sure", "done", "now", "not",
    "just", "still", "also", "from", "waiting", "ready", "coming", "going",
    "looking", "calling", "asking", "sending", "interested", "the", "sending",
    "at", "in", "on", "for", "with", "customer", "agent", "laundry", "khalas",
})


def scrub_conversational_names(text: str | None) -> str:
    """Mask first names volunteered after an introduction phrase → '[NAME]'.

    Deterministic and targeted: only capitalised tokens following an explicit
    intro phrase are masked, and only when the first token is not a common
    non-name word. Leaves the intro phrase intact ('this is [NAME]')."""
    if not text:
        return ""

    def _repl(m: re.Match) -> str:
        first = m.group("name").split()[0].lower()
        if first in _NOT_A_NAME:
            return m.group(0)  # not a name — leave untouched
        return m.group("lead") + "[NAME]"

    return _INTRO_NAME.sub(_repl, str(text))


# Record fields that must always be dropped entirely (never masked-in-place).
_DROP_FIELDS = frozenset({
    "phone", "phone_e164", "customer_phone", "email", "customer_email",
    "pickup_address", "address", "payment_method", "payment_link", "media_url",
    "photo_url", "api_key", "notes",
})
_TEXT_FIELDS = frozenset({
    "message", "text", "combined_turn", "expected_response", "description",
})


def sanitize_record(record: dict, *, names: list[str] | None = None) -> dict:
    """Return a sanitised copy of an eval record: drop raw-PII fields entirely and
    scrub PII from free-text fields."""
    out: dict = {}
    for k, v in record.items():
        if k in _DROP_FIELDS:
            continue
        if isinstance(v, str) and (k in _TEXT_FIELDS or len(v) > 30):
            out[k] = sanitize_text(v, mask_names=bool(names), names=names)
        elif isinstance(v, list):
            out[k] = [sanitize_text(x, mask_names=bool(names), names=names)
                      if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out
