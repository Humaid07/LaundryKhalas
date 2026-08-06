"""Customer-feedback detection + scope classification (pure).

Detects explicit corrections/preferences/complaints in a customer message and
classifies each as customer-specific (may become durable memory after validation)
vs global (must be queued for authorized Operations review — never auto-applied).
Pure keyword/pattern logic; the LLM does not decide what becomes a rule.
"""

from __future__ import annotations

import re

# feedback type constants (spec §22)
CUSTOMER_CORRECTION = "CUSTOMER_CORRECTION"
CUSTOMER_PREFERENCE = "CUSTOMER_PREFERENCE"
NEGATIVE_RESPONSE_FEEDBACK = "NEGATIVE_RESPONSE_FEEDBACK"
REPEATED_QUESTION_FEEDBACK = "REPEATED_QUESTION_FEEDBACK"
PRICE_FEEDBACK = "PRICE_FEEDBACK"
SERVICE_CLASSIFICATION_FEEDBACK = "SERVICE_CLASSIFICATION_FEEDBACK"
ORDER_ASSOCIATION_CORRECTION = "ORDER_ASSOCIATION_CORRECTION"
PAYMENT_PREFERENCE = "PAYMENT_PREFERENCE"
ADDRESS_CORRECTION = "ADDRESS_CORRECTION"
NAME_CORRECTION = "NAME_CORRECTION"
CONTACT_PREFERENCE = "CONTACT_PREFERENCE"

# scope
CUSTOMER = "customer"   # may become durable customer memory (after validation)
GLOBAL = "global"       # must be reviewed by Operations before changing behaviour
ORDER = "order"         # applies to this order only

# feedback type -> default scope.
_TYPE_SCOPE = {
    NAME_CORRECTION: CUSTOMER, ADDRESS_CORRECTION: CUSTOMER, CONTACT_PREFERENCE: CUSTOMER,
    PAYMENT_PREFERENCE: CUSTOMER, CUSTOMER_PREFERENCE: CUSTOMER,
    NEGATIVE_RESPONSE_FEEDBACK: GLOBAL, REPEATED_QUESTION_FEEDBACK: GLOBAL,
    SERVICE_CLASSIFICATION_FEEDBACK: GLOBAL, PRICE_FEEDBACK: GLOBAL,
    ORDER_ASSOCIATION_CORRECTION: ORDER, CUSTOMER_CORRECTION: CUSTOMER,
}

_ORDER_ONLY_RE = re.compile(r"\b(for this order|this order only|just this order|this time)\b", re.I)
_ALWAYS_RE = re.compile(r"\b(always|every time|from now on)\b", re.I)

# (regex, feedback_type). First match per type wins; multiple types may fire.
_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bmy name is\b.*\bnot\b|\bnot\b.*\bit'?s\b|misspell", re.I), NAME_CORRECTION),
    (re.compile(r"\bmy name is\b", re.I), NAME_CORRECTION),
    (re.compile(r"not my address|wrong address|my address is( now)?|different address", re.I), ADDRESS_CORRECTION),
    (re.compile(r"\bdo not call\b|don'?t call|whatsapp only|only whatsapp|no calls?", re.I), CONTACT_PREFERENCE),
    (re.compile(r"cash on delivery|\bcod\b|pay cash|use stripe|card payment|pay by card|do not call.*bank", re.I), PAYMENT_PREFERENCE),
    (re.compile(r"keep asking|asking the same|already (told|said|gave)|i already", re.I), REPEATED_QUESTION_FEEDBACK),
    (re.compile(r"too long|shorter|so long|reply is long|replies are (always )?too long", re.I), NEGATIVE_RESPONSE_FEEDBACK),
    (re.compile(r"price.*(wrong|incorrect|not right)|wrong price|overcharg", re.I), PRICE_FEEDBACK),
    (re.compile(r"wrong service|not that service|different service|already told you the service", re.I), SERVICE_CLASSIFICATION_FEEDBACK),
    (re.compile(r"another order|different order|other order|not this order", re.I), ORDER_ASSOCIATION_CORRECTION),
    (re.compile(r"\balways\b.*\b(address|whatsapp|reception|pickup|collect)\b", re.I), CUSTOMER_PREFERENCE),
)


def detect_feedback(text: str | None) -> list[dict]:
    """Return the list of detected feedback events for a message: each
    ``{feedback_type, scope}`` with scope adjusted for 'always' / 'for this order'."""
    body = (text or "").strip()
    if not body:
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for rx, ftype in _PATTERNS:
        if ftype in seen:
            continue
        if rx.search(body):
            seen.add(ftype)
            found.append({"feedback_type": ftype, "scope": classify_scope(ftype, body)})
    return found


def classify_scope(feedback_type: str, text: str) -> str:
    """customer / global / order for a feedback type + its message text."""
    if _ORDER_ONLY_RE.search(text or ""):
        return ORDER
    base = _TYPE_SCOPE.get(feedback_type, GLOBAL)
    # An explicit "always/every time" promotes a preference to durable customer scope.
    if base == CUSTOMER and _ALWAYS_RE.search(text or ""):
        return CUSTOMER
    return base


def is_global(feedback_type: str, text: str) -> bool:
    return classify_scope(feedback_type, text) == GLOBAL
