"""Classifier prompt construction.

The system prompt is a STABLE, cacheable prefix: instructions + the full closed
taxonomy + the compact service-alias hint. It is byte-identical across every
request (no per-customer data), so it is marked for the 1h prompt cache and the
per-turn payload (customer message + state) is the only thing that changes
(spec: "Keep dynamic data outside the shared cache").

The service-alias hint is a small, stable map so the model maps phrases to
SERVICE_DOMAINS consistently; the backend service resolver remains authoritative
for the actual booking (the classifier only labels).
"""
from __future__ import annotations

import json

from classifier import taxonomy as tax
from classifier.context import ClassifierInput

# A small, STABLE alias hint (ordering fixed). This is guidance only — the
# backend catalogue/service_resolution remains the source of truth for booking.
_SERVICE_ALIAS_HINT: dict[str, list[str]] = {
    "WASH_AND_FOLD": ["wash and fold", "wash & fold"],
    "CLEAN_AND_PRESS": ["dry cleaning", "wash and iron", "clean and press"],
    "PRESS_ONLY": ["ironing", "steam press", "press only"],
    "CARPETS_AND_RUGS": ["carpet", "rug"],
    "CURTAINS": ["curtain", "drapes"],
    "BEDDING_AND_HOME_TEXTILES": ["bedding", "duvet", "blanket"],
    "SOFA_AND_UPHOLSTERY": ["sofa", "couch", "upholstery"],
    "SHOES": ["shoes", "sneakers"],
    "BAGS_AND_ACCESSORIES": ["handbag", "purse", "bag"],
    "ALTERATIONS_AND_GARMENT_REPAIR": ["alteration", "shorten", "hem", "stitch", "torn"],
    "WEDDING_AND_EVENING_DRESSES": ["wedding dress", "evening gown"],
    "LEATHER": ["leather jacket"],
    "SUITS_AND_BLAZERS": ["suit", "blazer"],
    "TRADITIONAL_WEAR": ["kandura", "abaya", "thobe"],
    "RESTORATION": ["restore", "colour restoration"],
    "EXPRESS": ["express", "same day", "urgent"],
    "B2B_COMMERCIAL": ["hotel", "restaurant", "uniforms", "commercial linen"],
}


def _taxonomy_block() -> str:
    """The closed vocabularies, rendered stably. Any reordering busts the cache,
    so this is derived deterministically from the (stable) taxonomy tuples."""
    lines = [
        "PRIMARY_INTENTS: " + ", ".join(tax.PRIMARY_INTENTS),
        "CUSTOMER_GOALS: " + ", ".join(tax.CUSTOMER_GOALS),
        "CONVERSATION_ROUTES: " + ", ".join(tax.CONVERSATION_ROUTES),
        "FIXED_TEMPLATE_IDS: " + ", ".join(tax.FIXED_TEMPLATE_IDS),
        "SERVICE_DOMAINS: " + ", ".join(tax.SERVICE_DOMAINS),
        "PRICING_INTENTS: " + ", ".join(tax.PRICING_INTENTS),
        "PAYMENT_INTENTS: " + ", ".join(tax.PAYMENT_INTENTS),
        "REPAIR_INTENTS: " + ", ".join(tax.REPAIR_INTENTS),
        "COMPLAINT_TYPES: " + ", ".join(tax.COMPLAINT_TYPES),
        "SENTIMENTS: " + ", ".join(tax.SENTIMENTS),
        "URGENCIES: " + ", ".join(tax.URGENCIES),
        "CLARIFICATION_TOPICS: " + ", ".join(tax.CLARIFICATION_TOPICS),
        "HUMAN_REASONS: " + ", ".join(tax.HUMAN_REASONS),
        "REASON_CODES: " + ", ".join(tax.REASON_CODES),
    ]
    return "\n".join(lines)


# Built once at import; stable for the process lifetime → cacheable prefix.
SYSTEM_PROMPT = f"""\
You are the LaundryKhalas WhatsApp INTENT CLASSIFIER. You are an internal routing
component. You NEVER write a customer-facing message, never calculate a price,
discount, pickup slot or any operational value, and never decide business rules.
You output exactly one structured classification of the customer's latest logical
turn by calling the `{ '{tool}' }` tool, using ONLY the allowed enum values below.

Hard rules:
- Return ONE classification object via the tool. No prose, no explanation, no
  chain-of-thought. reason_codes must be from the predefined REASON_CODES list.
- Do NOT invent the customer lifecycle — it is provided in the payload.
- Support multiple intents: put the dominant one in primary_intent and the rest
  in secondary_intents. Never drop an intent just because another came first.
- "dry cleaning" → CLEAN_AND_PRESS unless the context is clearly leather / shoes /
  bags / restoration. "laundry" alone stays GENERAL_ENQUIRY until clarified.
  "wash and iron" → CLEAN_AND_PRESS. "ironing"/"steam press" → PRESS_ONLY.
- "repair" is NEVER automatically UNSUPPORTED_REQUEST. Only non-laundry items
  (phone, laptop, car, watch, furniture) are UNSUPPORTED_REQUEST with reason
  NON_LAUNDRY_REPAIR. An ambiguous repair → REPAIR_REQUEST + AMBIGUOUS_REPAIR +
  needs_clarification=true.
- Detect price resistance (PRICE_PUSHBACK) and discount asks (DISCOUNT_REQUEST)
  but NEVER compute or approve a discount — the backend engine does that.
- Distinguish PICKUP_SLOT_ENQUIRY (asking what's available) from
  EXACT_PICKUP_TIME_REQUEST (naming a specific time) from PICKUP_SLOT_SELECTION
  (choosing an already-offered option — only when slot options are active).
- Distinguish Stripe vs cash payment intents. A duplicate/twice charge is a
  COMPLAINT with payment_intent=DUPLICATE_CHARGE and requires_human=true.
- "Where is my order?" is a status enquiry, NOT automatically a complaint. It
  becomes a complaint only with an explicit grievance (e.g. "no update for days").
- Set requires_human=true and the matching human_reason for mandatory cases:
  refunds, damage, missing/wrong item, payment disputes, duplicate charges,
  repeated failed pickup/delivery, reprocessing, explicit human/manager request,
  serious abuse or credible threats. Bias toward escalation when evidence is clear.
- Do NOT over-escalate mild price negotiation as anger.
- should_cancel_followups=true for any genuine customer reply.
- If confidence is low or the turn is a bare short reply with no relevant context,
  use UNKNOWN / NEEDS_CLARIFICATION rather than guessing a destructive action.

CLOSED VOCABULARIES (use these exact values):
{_taxonomy_block()}

SERVICE ALIAS HINT (guidance only; backend resolver is authoritative):
{json.dumps(_SERVICE_ALIAS_HINT, ensure_ascii=False)}
""".replace("{tool}", "emit_classification")


def build_user_payload(ci: ClassifierInput) -> str:
    """The dynamic per-turn content (NOT cached). Compact JSON = the spec's
    classifier input shape, PII-safe by construction (see context.py)."""
    return json.dumps(ci.to_payload(), ensure_ascii=False)
