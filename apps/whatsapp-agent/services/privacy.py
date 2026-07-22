"""Privacy firewall helpers (RULE 8 / CLAUDE.md §7).

Masks obvious PII — phone numbers and email addresses — before it is
written to the agent audit log (agent_logs) or any facility-facing /
driver-facing output. The raw conversation transcript itself (messages
table) is kept intact, because multi-turn slot filling needs the real
words the customer typed; masking is applied to the *derived* audit/
analytics trail and to outward, role-restricted views — not to the
conversation record the agent reasons over.

Deliberately conservative: only phone-shaped digit runs (8+ digits) and
emails are masked, so short tokens like an order ID (LK-1023) or a pickup
time (7pm) are never mangled.
"""
import hashlib
import re

# 8+ "phone-ish" characters, not glued to a word char on either side, so a
# 4-digit order number or a time like "7pm" is not treated as a phone.
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

PHONE_PLACEHOLDER = "[phone hidden]"
EMAIL_PLACEHOLDER = "[email hidden]"


def mask_pii(text: str | None) -> str | None:
    """Return `text` with emails and phone numbers replaced by placeholders.
    None/empty passes through unchanged."""
    if not text:
        return text
    masked = _EMAIL.sub(EMAIL_PLACEHOLDER, text)
    masked = _PHONE.sub(PHONE_PLACEHOLDER, masked)
    return masked


def mask_phone(phone: str | None) -> str:
    """Human-safe masked phone for the `masked_phone` column / any display —
    keeps the leading country/prefix and last 2 digits, masks the middle
    (e.g. '+971 50 •••• 24'). The full number is stored only in phone_e164
    (backend-only, used to send) and never returned by the read APIs."""
    digits = re.sub(r"[^\d+]", "", phone or "")
    if len(digits) < 6:
        return "•••• ••••"
    return f"{digits[:5]} •••• {digits[-2:]}"


def normalize_e164(phone: str | None) -> str:
    """Best-effort E.164 normalization for COMPARING WhatsApp senders across the
    several shapes Evolution/Baileys emits, so we never string-compare raw values:

        '971502485658@s.whatsapp.net' -> '+971502485658'
        'whatsapp:+971502485658'      -> '+971502485658'
        '+971 50 248 5658'            -> '+971502485658'
        '971502485658'                -> '+971502485658'

    Returns '+<digits>' or '' when there are no digits. This is a comparison key,
    not a validator — it does not check country codes or length.
    """
    if not phone:
        return ""
    raw = phone.strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1]
    raw = raw.split("@", 1)[0]  # drop a JID domain (@s.whatsapp.net / @g.us)
    digits = re.sub(r"[^\d]", "", raw)
    return f"+{digits}" if digits else ""


def hash_phone(phone: str | None) -> str:
    """Stable, non-reversible hash of the phone digits — used to look up / dedupe
    a customer without scattering extra copies of the raw number."""
    digits = re.sub(r"[^\d]", "", phone or "")
    return hashlib.sha256(digits.encode()).hexdigest() if digits else ""
