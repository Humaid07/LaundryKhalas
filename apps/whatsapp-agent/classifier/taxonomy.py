"""Classifier taxonomy — the closed vocabularies the classifier may emit.

Every list here is ORDER-STABLE on purpose: the taxonomy is rendered into the
cacheable classifier prompt prefix, so re-ordering it would bust the Anthropic
prompt cache on every request (spec: "Keep the classifier prompt and enum
ordering stable to improve cache reuse"). Add new values at the END of a list.

These are plain string tuples (mirroring services/abuse_classification.py's
config-driven style) rather than Enums — the values ARE the wire format that
goes to the model and into the database, so we keep them as bare strings and
validate membership explicitly.
"""
from __future__ import annotations

# --- version -----------------------------------------------------------------
# Bump when the taxonomy or prompt changes in a way that makes old rows
# non-comparable. Mirrors WHATSAPP_CLASSIFIER_RULESET_VERSION.
CLASSIFICATION_VERSION = "2026_08_05"

# --- primary intents ---------------------------------------------------------
PRIMARY_INTENTS: tuple[str, ...] = (
    "GREETING",
    "SMALL_TALK",
    "GENERAL_ENQUIRY",
    "SERVICE_ENQUIRY",
    "SERVICE_SELECTION",
    "BOOKING_START",
    "BOOKING_CONTINUE",
    "PRICE_ENQUIRY",
    "PRICE_PUSHBACK",
    "DISCOUNT_REQUEST",
    "PROCESS_ENQUIRY",
    "ADDRESS_PROVIDED",
    "LOCATION_PIN_PROVIDED",
    "PICKUP_SLOT_ENQUIRY",
    "PICKUP_SLOT_SELECTION",
    "EXACT_PICKUP_TIME_REQUEST",
    "EXPRESS_SERVICE_REQUEST",
    "ORDER_SUMMARY_REQUEST",
    "ORDER_CONFIRMATION",
    "ORDER_CHANGE",
    "ORDER_CANCELLATION",
    "PAYMENT_METHOD_ENQUIRY",
    "STRIPE_PAYMENT_QUERY",
    "CASH_PAYMENT_REQUEST",
    "PAYMENT_PROBLEM",
    "ORDER_STATUS_ENQUIRY",
    "PICKUP_STATUS_ENQUIRY",
    "DELIVERY_STATUS_ENQUIRY",
    "REPAIR_REQUEST",
    "ALTERATION_REQUEST",
    "SPECIALIST_RESTORATION_REQUEST",
    "PHOTO_OR_MEDIA_PROVIDED",
    "FACILITY_QUOTE_FOLLOWUP",
    "COMPLAINT",
    "REFUND_REQUEST",
    "REPROCESSING_REQUEST",
    "HUMAN_AGENT_REQUEST",
    "B2B_ENQUIRY",
    "FEEDBACK_OR_REVIEW",
    "OPT_OUT",
    "UNSUPPORTED_REQUEST",
    "UNKNOWN",
)

# --- customer goal -----------------------------------------------------------
CUSTOMER_GOALS: tuple[str, ...] = (
    "GET_INFORMATION",
    "CHECK_SERVICE_AVAILABILITY",
    "GET_PRICE",
    "NEGOTIATE_PRICE",
    "PLACE_ORDER",
    "CONTINUE_ORDER",
    "CHANGE_ORDER",
    "CONFIRM_ORDER",
    "CANCEL_ORDER",
    "CHECK_STATUS",
    "MAKE_PAYMENT",
    "CHANGE_PAYMENT_METHOD",
    "REPORT_PROBLEM",
    "REQUEST_REFUND",
    "REQUEST_REPROCESSING",
    "REQUEST_HUMAN",
    "PROVIDE_INFORMATION",
    "COMMERCIAL_ENQUIRY",
    "END_CONVERSATION",
    "UNKNOWN",
)

# --- conversation route (classifier RECOMMENDS one; backend validates) -------
CONVERSATION_ROUTES: tuple[str, ...] = (
    "DETERMINISTIC_HANDLER",
    "MAIN_AGENT",
    "HUMAN_INTERVENTION",
    "OPERATIONS_EVENT",
    "IGNORE",
    "NEEDS_CLARIFICATION",
)

# --- fixed deterministic response templates (classifier may SUGGEST an id) ---
FIXED_TEMPLATE_IDS: tuple[str, ...] = (
    "GREETING_NEW_CUSTOMER",
    "GREETING_RETURNING_CUSTOMER",
    "ASK_SERVICE",
    "ASK_ADDRESS_AND_PIN",
    "ASK_PIN_ONLY",
    "ASK_ADDRESS_DETAILS_ONLY",
    "CONFIRM_SAVED_ADDRESS",
    "PROCESS_EXPLANATION",
    "MINIMUM_ORDER_ADD_ITEM",
    "MINIMUM_ORDER_DELIVERY_FEE",
    "PICKUP_SLOT_OPTIONS",
    "PICKUP_SLOT_CONFIRMATION",
    "EXACT_PRICE_RESPONSE",
    "FROM_PRICE_RESPONSE",
    "FACILITY_QUOTE_PENDING",
    "INSPECTION_DISCOUNT_PENDING",
    "STRIPE_REGULAR_PAYMENT",
    "STRIPE_ACCOUNT_NOT_REQUIRED",
    "CASH_ON_DELIVERY_ACCEPTED",
    "PAYMENT_FOLLOWUP_STRIPE",
    "PAYMENT_FOLLOWUP_CASH",
    "ORDER_SUMMARY",
    "ORDER_CONFIRMED",
    "HUMAN_HANDOVER",
    "REPAIR_CLARIFICATION",
    "OPT_OUT_CONFIRMATION",
)

# --- service domains (validated against the catalogue resolver, see prompt) --
SERVICE_DOMAINS: tuple[str, ...] = (
    "WASH_AND_FOLD",
    "CLEAN_AND_PRESS",
    "PRESS_ONLY",
    "DRY_CLEANING_ALIAS",
    "BEDDING_AND_HOME_TEXTILES",
    "CURTAINS",
    "CARPETS_AND_RUGS",
    "SOFA_AND_UPHOLSTERY",
    "SHOES",
    "BAGS_AND_ACCESSORIES",
    "ALTERATIONS_AND_GARMENT_REPAIR",
    "WEDDING_AND_EVENING_DRESSES",
    "LEATHER",
    "TOYS_AND_MASCOTS",
    "RESTORATION",
    "TRADITIONAL_WEAR",
    "SUITS_AND_BLAZERS",
    "EXPRESS",
    "B2B_COMMERCIAL",
    "MULTI_SERVICE",
    "UNKNOWN",
)

# --- pricing intent ----------------------------------------------------------
# QUOTE_INACTIVITY intentionally EXCLUDED: it is scheduler-derived from
# timestamps, never emitted from a customer message (spec).
PRICING_INTENTS: tuple[str, ...] = (
    "NONE",
    "ASKING_PRICE",
    "ASKING_TOTAL",
    "ASKING_RATE",
    "ASKING_MINIMUM_ORDER",
    "ASKING_DELIVERY_CHARGE",
    "PRICE_PUSHBACK",
    "ASKING_DISCOUNT",
    "COMPARING_PRICE",
    "ACCEPTING_PRICE",
    "DECLINING_PRICE",
)

# --- payment intent ----------------------------------------------------------
PAYMENT_INTENTS: tuple[str, ...] = (
    "NONE",
    "ASKING_PAYMENT_METHODS",
    "ASKING_ABOUT_STRIPE",
    "STRIPE_ACCEPTED",
    "STRIPE_ACCOUNT_CONCERN",
    "STRIPE_FAILED",
    "CASH_ENQUIRY",
    "CASH_PREFERENCE",
    "CASH_CONFIRMED",
    "PAYMENT_ALREADY_MADE",
    "PAYMENT_DISPUTE",
    "DUPLICATE_CHARGE",
)

# --- repair intent -----------------------------------------------------------
REPAIR_INTENTS: tuple[str, ...] = (
    "NONE",
    "AMBIGUOUS_REPAIR",
    "STANDARD_ALTERATION",
    "STANDARD_GARMENT_REPAIR",
    "SHOE_REPAIR",
    "BAG_REPAIR",
    "LEATHER_REPAIR",
    "SPECIALIST_RESTORATION",
    "UNSUPPORTED_NON_LAUNDRY_REPAIR",
)

# --- complaint type ----------------------------------------------------------
COMPLAINT_TYPES: tuple[str, ...] = (
    "NONE",
    "GENERAL_DISSATISFACTION",
    "PICKUP_DELAY",
    "REPEATED_FAILED_PICKUP",
    "DELIVERY_DELAY",
    "REPEATED_FAILED_DELIVERY",
    "NO_UPDATE",
    "CLEANING_QUALITY",
    "ALTERATION_QUALITY",
    "DAMAGE_CLAIM",
    "MISSING_ITEM",
    "WRONG_ITEM",
    "WRONG_DELIVERY",
    "PAYMENT_DISPUTE",
    "DUPLICATE_CHARGE",
    "LUXURY_ITEM_DISPUTE",
    "REFUND_REQUEST",
    "LEGAL_THREAT",
    "ABUSE_OR_HARASSMENT",
    "CREDIBLE_THREAT",
    "OTHER_COMPLAINT",
)

# --- sentiment / urgency -----------------------------------------------------
SENTIMENTS: tuple[str, ...] = (
    "POSITIVE",
    "NEUTRAL",
    "CONFUSED",
    "NEGATIVE",
    "ANGRY",
)

FRUSTRATION_LEVELS: tuple[int, ...] = (0, 1, 2, 3)

URGENCIES: tuple[str, ...] = (
    "LOW",
    "NORMAL",
    "HIGH",
    "CRITICAL",
)

# --- clarification topics (classifier signals; the MAIN agent asks) ----------
CLARIFICATION_TOPICS: tuple[str, ...] = (
    "SERVICE_REQUIRED",
    "REPAIR_ITEM_AND_SCOPE",
    "ITEM_TYPE_REQUIRED",
    "SERVICE_VARIANT_REQUIRED",
    "ORDER_REFERENCE_REQUIRED",
    "PAYMENT_ISSUE_REQUIRED",
    "ADDRESS_DETAILS_REQUIRED",
    "LOCATION_PIN_REQUIRED",
    "PHOTO_CONTEXT_REQUIRED",
    "B2B_REQUIREMENT_REQUIRED",
    "UNSUPPORTED_CONTEXT_REQUIRED",
    "UNKNOWN_INTENT",
)

# --- mandatory human-intervention reasons ------------------------------------
# When ANY of these is the human_reason, the backend MUST create the
# intervention atomically (deterministic layer also enforces a subset).
HUMAN_REASONS: tuple[str, ...] = (
    "REFUND_REQUEST",
    "DAMAGE_CLAIM",
    "MISSING_ITEM",
    "WRONG_ITEM",
    "WRONG_DELIVERY",
    "PAYMENT_DISPUTE",
    "DUPLICATE_CHARGE",
    "LEGAL_THREAT",
    "REPEATED_FAILED_PICKUP",
    "REPEATED_FAILED_DELIVERY",
    "LUXURY_ITEM_DISPUTE",
    "CUSTOMER_REQUESTED_HUMAN",
    "CUSTOMER_REQUESTED_MANAGER",
    "CUSTOMER_REQUESTED_SUPERVISOR",
    "CUSTOMER_REQUESTED_OPERATIONS",
    "REPROCESSING_REQUEST",
    "REPEATED_UNPROCESSABLE_VOICE_MESSAGE",
    "SERIOUS_ABUSE",
    "CREDIBLE_THREAT",
)

# The subset of human reasons that the deterministic layer / validated
# classifier treat as MANDATORY escalation (used for recall metrics + the
# "bias toward escalation when evidence is clear" rule).
MANDATORY_HUMAN_REASONS: frozenset[str] = frozenset(HUMAN_REASONS)

# --- customer lifecycle (BACKEND-resolved, never invented by the model) ------
LIFECYCLE_STAGES: tuple[str, ...] = (
    "NEW_PROSPECT",
    "RETURNING_PROSPECT",
    "EXISTING_CUSTOMER",
    "ACTIVE_CUSTOMER",
    "B2B_LEAD",
)

# --- reason codes (concise, predefined; NOT free-form explanations) ----------
REASON_CODES: tuple[str, ...] = (
    "EXPLICIT_SERVICE_MENTION",
    "IMPLICIT_SERVICE_MENTION",
    "GREETING_ONLY",
    "PRICE_KEYWORD",
    "PRICE_RESISTANCE_PHRASE",
    "DISCOUNT_PHRASE",
    "PROCESS_QUESTION",
    "ADDRESS_TEXT",
    "LOCATION_EVENT",
    "SLOT_ENQUIRY_PHRASE",
    "EXACT_TIME_PHRASE",
    "SLOT_SELECTION_IN_CONTEXT",
    "CONFIRMATION_IN_CONTEXT",
    "SHORT_REPLY_IN_CONTEXT",
    "REPAIR_KEYWORD",
    "ALTERATION_KEYWORD",
    "RESTORATION_KEYWORD",
    "NON_LAUNDRY_REPAIR",
    "PAYMENT_METHOD_QUESTION",
    "STRIPE_KEYWORD",
    "CASH_KEYWORD",
    "PAYMENT_DISPUTE_PHRASE",
    "STATUS_QUESTION",
    "COMPLAINT_PHRASE",
    "REPEATED_FAILURE_PHRASE",
    "DAMAGE_PHRASE",
    "MISSING_ITEM_PHRASE",
    "REFUND_PHRASE",
    "REPROCESSING_PHRASE",
    "HUMAN_REQUEST_PHRASE",
    "B2B_SIGNAL",
    "MULTI_INTENT",
    "OPT_OUT_KEYWORD",
    "FEEDBACK_PHRASE",
    "LOW_CONFIDENCE",
    "NO_CONTEXT_FOR_SHORT_REPLY",
    "DETERMINISTIC_EVENT",
    "CLASSIFIER_FAILED",
    "UNSUPPORTED_TOPIC",
)


def is_valid(value: str | int | None, vocabulary: tuple) -> bool:
    """True when ``value`` is a member of a closed vocabulary (or None where the
    field is optional). Used by schema validation to reject anything the model
    emits outside the taxonomy rather than persisting a junk label."""
    return value is None or value in vocabulary
