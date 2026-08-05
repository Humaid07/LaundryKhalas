"""Website "Order Now" intent + abandonment decision (spec §24) — pure & deterministic.

Clicking Order Now on the website opens a WhatsApp chat, but a click alone does NOT
reveal the visitor's number, and a prefilled-but-unsent WhatsApp message is NOT an
inbound conversation. So outreach is strictly gated:

  * ALWAYS record the intent event (for analytics), identified or not.
  * Schedule the three abandonment follow-ups (§24) ONLY for an identified, consented
    visitor with a VERIFIED WhatsApp number. No number or no consent → log the anonymous
    event and schedule nothing.
  * NEVER fingerprint / guess a number from browser data.

This module only decides; the endpoint persists the event and (when allowed) queues the
follow-ups via services/followup_scheduler.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.privacy import normalize_e164


@dataclass
class WebOrderIntentInput:
    session_id: str
    source_page: str | None = None
    service_code: str | None = None
    market: str = "AE"
    campaign: dict = field(default_factory=dict)   # UTM / campaign attribution
    whatsapp_number: str | None = None             # only if the visitor supplied+verified it
    consent: bool = False                          # explicit consent to WhatsApp outreach
    customer_id: str | None = None                 # set when the visitor is signed in


@dataclass(frozen=True)
class IntentDecision:
    schedule_outreach: bool
    reason: str                    # identified_consented | no_verified_number | no_consent
    normalized_number: str | None


def evaluate_intent(intent: WebOrderIntentInput) -> IntentDecision:
    """Decide whether to schedule abandonment outreach. Outreach requires BOTH a valid
    E.164 WhatsApp number AND explicit consent (spec §24). No fingerprinting: the number
    must have been supplied by the visitor, never inferred."""
    number = normalize_e164(intent.whatsapp_number or "")
    if not number:
        return IntentDecision(False, "no_verified_number", None)
    if not intent.consent:
        return IntentDecision(False, "no_consent", number)
    return IntentDecision(True, "identified_consented", number)
