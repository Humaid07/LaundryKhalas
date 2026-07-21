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
