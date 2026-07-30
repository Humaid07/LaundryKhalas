"""Customer identity from the WhatsApp channel — phone + profile name.

Backend is authoritative. Claude may *suggest* whether a name looks valid, but the
final accept/reject decision and the normalized number are decided here.

  * ``normalize_whatsapp_sender_number`` — turn an Evolution sender identifier into
    a validated E.164 number (reuses services.privacy.normalize_e164, then applies
    real E.164 length/shape validation).
  * ``validate_whatsapp_profile_name`` — decide whether a WhatsApp pushName is a
    plausible *personal* name (rejects device names, slogans, phone/email/url,
    emoji/punctuation-only, generic placeholders). Supports Unicode scripts.
  * ``resolve_customer_identity`` — apply the name precedence rules.

Pure functions only — no DB, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.privacy import normalize_e164

# --- Phone -----------------------------------------------------------------

# E.164: '+' then a country-code digit 1-9 then up to 14 more digits (8-15 total).
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_whatsapp_sender_number(raw: str | None) -> tuple[str | None, bool]:
    """Return ``(e164, is_valid)``.

    Strips WhatsApp/JID/device decoration then validates true E.164 shape. When it
    cannot be validated, returns ``(candidate_or_None, False)`` so the caller can
    ask the customer or flag Operations — it never fabricates a number.
    """
    if not raw:
        return None, False
    # Drop a Baileys ':device' suffix before the JID domain, then reuse the
    # shared normalizer for the rest of the shapes.
    pre = raw.split("@", 1)[0].split(":", 1)[0]
    e164 = normalize_e164(pre) or normalize_e164(raw)
    if not e164:
        return None, False
    return (e164, True) if _E164_RE.match(e164) else (e164, False)


# --- Profile name ----------------------------------------------------------

# Lowercased single-word tokens that are never a personal name.
_DEVICE_TOKENS = {
    "iphone", "ipad", "ipod", "samsung", "galaxy", "redmi", "xiaomi", "huawei",
    "oppo", "vivo", "nokia", "android", "phone", "mobile", "device", "tablet",
}
_GENERIC_TOKENS = {
    "unknown", "customer", "guest", "user", "admin", "test", "testing", "none",
    "na", "null", "team", "staff", "support", "sales", "info", "contact",
    "laundry", "khalas", "khalaas", "dryclean",
}
_BUSINESS_TOKENS = {
    "deals", "deal", "discount", "offer", "offers", "sale", "promo", "promotion",
    "best", "cheap", "official", "store", "shop", "services", "service", "company",
    "marketing", "agency", "trading", "ltd", "llc", "inc", "co", "enterprise",
    "solutions", "group", "rentals", "rental", "properties", "realestate",
    "crypto", "forex", "investment", "loan", "loans",
}
_DENY_TOKENS = _DEVICE_TOKENS | _GENERIC_TOKENS | _BUSINESS_TOKENS

# Multi-word slogan/placeholder phrases (substring match, lowercased).
_DENY_PHRASES = (
    "work phone", "home phone", "my phone", "no name", "new number", "old number",
    "not available", "do not disturb", "real estate", "for sale", "best price",
)

_URL_MARKERS = ("http://", "https://", "www.", ".com", ".net", ".org", ".ae", ".io")


@dataclass(frozen=True)
class NameCheck:
    valid: bool
    reason: str
    cleaned: str


def validate_whatsapp_profile_name(raw: str | None) -> NameCheck:
    """Decide whether ``raw`` (a WhatsApp pushName) is a plausible personal name."""
    name = (raw or "").strip()
    if not name:
        return NameCheck(False, "empty", "")
    if len(name) < 2:
        return NameCheck(False, "too_short", name)
    if len(name) > 40:
        return NameCheck(False, "too_long", name)

    # Must contain at least one alphabetic character (covers digits-only,
    # punctuation-only and emoji-only rejections across all scripts).
    if not any(ch.isalpha() for ch in name):
        return NameCheck(False, "no_letters", name)

    if "@" in name:
        return NameCheck(False, "email_like", name)

    low = name.lower()
    if any(marker in low for marker in _URL_MARKERS):
        return NameCheck(False, "url_like", name)

    # Phone-like: 6+ digits total.
    if sum(ch.isdigit() for ch in name) >= 6:
        return NameCheck(False, "phone_like", name)

    if any(phrase in low for phrase in _DENY_PHRASES):
        return NameCheck(False, "placeholder_or_slogan", name)

    ascii_tokens = set(re.findall(r"[a-z]+", low))
    if ascii_tokens & _DENY_TOKENS:
        return NameCheck(False, "device_generic_or_business", name)

    return NameCheck(True, "ok", name)


# --- Name precedence -------------------------------------------------------

SOURCE_CUSTOMER_PROVIDED = "CUSTOMER_PROVIDED"
SOURCE_CONFIRMED = "CONFIRMED"
SOURCE_WHATSAPP_PROFILE = "WHATSAPP_PROFILE"
SOURCE_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ResolvedName:
    name: str | None
    source: str
    confidence: float
    requires_confirmation: bool


def resolve_customer_identity(
    *,
    explicit_name: str | None = None,
    confirmed_name: str | None = None,
    whatsapp_profile_name: str | None = None,
) -> ResolvedName:
    """Apply precedence: explicit > confirmed > valid profile name > ask.

    A valid profile name is used as the default (no separate name question); it is
    treated as implicitly confirmed when the customer accepts the order summary, so
    ``requires_confirmation`` is False for it. Only when nothing usable exists do we
    flag that the customer must be asked.
    """
    if explicit_name and explicit_name.strip():
        return ResolvedName(explicit_name.strip(), SOURCE_CUSTOMER_PROVIDED, 1.0, False)
    if confirmed_name and confirmed_name.strip():
        return ResolvedName(confirmed_name.strip(), SOURCE_CONFIRMED, 1.0, False)
    check = validate_whatsapp_profile_name(whatsapp_profile_name)
    if check.valid:
        return ResolvedName(check.cleaned, SOURCE_WHATSAPP_PROFILE, 0.7, False)
    return ResolvedName(None, SOURCE_UNKNOWN, 0.0, True)
