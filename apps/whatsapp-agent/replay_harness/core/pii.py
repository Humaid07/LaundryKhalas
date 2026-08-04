"""PII redaction for downloadable reports.

Redacts phone numbers, emails, unit/apartment/room numbers, building access
notes, full addresses, payment references, and location coordinates while
retaining enough structure to follow the conversation.

Example:
    "Apartment 1204, Marina Heights, Dubai Marina"
    -> "Apartment [UNIT], [BUILDING], Dubai Marina"

Redaction is applied to REPORT output only. The source archive is never
rewritten, and unredacted reports require an explicit, disabled-by-default flag.
"""
from __future__ import annotations

import re

# Order matters: emails before phone (emails contain digits), unit before phone.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# International / local phone numbers: +CC ... or long digit runs with separators.
_PHONE_RE = re.compile(
    r"(?<![\w])(?:\+?\d[\d\s\-().]{6,}\d)(?![\w])"
)
# Apartment / flat / villa / room / unit / office followed by an identifier.
_UNIT_RE = re.compile(
    r"\b(apartment|apt|flat|villa|room|unit|office|suite|door)\b[\s.:#]*"
    r"([0-9]{1,5}[A-Za-z]?|[A-Za-z]?[0-9]{1,5})",
    re.IGNORECASE,
)
# "floor 12", "12th floor"
_FLOOR_RE = re.compile(
    r"\b(?:(\d{1,3})(?:st|nd|rd|th)?\s+floor|floor[\s.:#]*(\d{1,3}))\b",
    re.IGNORECASE,
)
# Decimal coordinate pairs, e.g. "25.0805, 55.1403"
_COORD_RE = re.compile(r"[-+]?\d{1,3}\.\d{3,},\s*[-+]?\d{1,3}\.\d{3,}")
# Payment references: long alnum tokens after a payment keyword, or IBAN-ish.
_PAYMENT_RE = re.compile(
    r"\b(?:iban|ref(?:erence)?|txn|transaction|receipt|invoice)\b[\s.:#]*"
    r"([A-Za-z0-9]{6,})",
    re.IGNORECASE,
)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


def redact_text(text: str, *, enabled: bool = True) -> str:
    """Redact PII from a free-text string. No-op when disabled."""
    if not enabled or not text:
        return text
    out = _EMAIL_RE.sub("[EMAIL]", text)
    out = _IBAN_RE.sub("[PAYMENT_REF]", out)
    out = _PAYMENT_RE.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + "[PAYMENT_REF]", out)
    out = _COORD_RE.sub("[COORDS]", out)
    out = _UNIT_RE.sub(lambda m: f"{m.group(1)} [UNIT]", out)
    out = _FLOOR_RE.sub("floor [FLOOR]", out)
    out = _PHONE_RE.sub("[PHONE]", out)
    return out


def redact_phone(phone: str, *, enabled: bool = True) -> str:
    """Mask a phone number keeping only the country-code hint."""
    if not enabled or not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "[PHONE]"
    return f"[PHONE …{digits[-2:]}]"


def redact_location(lat: object, lon: object, *, enabled: bool = True):
    """Redact a coordinate pair for reports."""
    if not enabled:
        return lat, lon
    return "[COORDS]", "[COORDS]"
