"""Intent classification for the Laundry Class agent (task Part 5).

Deterministic keyword/pattern routing across the 15 required intents. Critical
intents (refund, damage, missing item, human support, payment dispute) are matched
first so they can never be shadowed by a generic pricing/service keyword. Short
contextual follow-ups ("yes", "at 6", "same address", "the blue one") are handled
by the caller via conversation state — this module reports `unknown` for them and
the graph resolves them from the in-progress order flow.
"""
from __future__ import annotations

import re

GREETING = "greeting"
PRICE = "price_enquiry"
SERVICE = "service_enquiry"
PICKUP_DELIVERY = "pickup_delivery_enquiry"
NEW_ORDER = "new_order"
ORDER_STATUS = "order_status"
DELIVERY_RESCHEDULE = "delivery_reschedule"
CANCELLATION = "cancellation"
REFUND = "refund_request"
DAMAGE = "damage_complaint"
MISSING_ITEM = "missing_item_complaint"
PAYMENT = "payment_question"
SPECIAL_ITEM = "special_item_enquiry"
HUMAN_SUPPORT = "human_support"
UNKNOWN = "unknown"

_GREETING = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|yo|good\s?(morning|afternoon|evening)|"
    r"(as-?)?salam(u)?\s?(a)?laikum|greetings)[\s!.,]*$",
    re.IGNORECASE,
)

# Ordered most-critical first; first category whose keyword appears wins.
_ORDERED_KEYWORDS: list[tuple[str, list[str]]] = [
    (HUMAN_SUPPORT, [
        "speak to a human", "speak to someone", "talk to a human", "talk to someone",
        "real person", "real human", "speak to a person", "customer service agent",
        "human agent", "speak to an agent", "talk to an agent", "call me", "agent please",
    ]),
    (DAMAGE, [
        "torn", "tear", "ripped", "rip ", "damaged", "damage", "ruined", "shrunk",
        "shrank", "shrinkage", "colour bleed", "color bleed", "bleeding", "stained it",
        "hole in", "burn mark", "faded", "discolou", "melted",
    ]),
    (MISSING_ITEM, [
        "missing", "lost my", "lost item", "didn't get back", "did not get back",
        "not returned", "you lost", "item is gone", "one is missing",
    ]),
    (REFUND, ["refund", "money back", "reimburse", "compensation", "compensate"]),
    (PAYMENT, [
        "charged twice", "double charged", "charged me twice", "overcharged",
        "paid but", "payment failed", "payment issue", "wrong amount",
        "how do i pay", "how can i pay", "payment method", "which payment",
    ]),
    (DELIVERY_RESCHEDULE, [
        "reschedule", "won't be home", "wont be home", "not be home", "not home",
        "change the delivery", "change my delivery", "come later", "come at",
        "deliver later", "different time", "another time", "push the delivery",
    ]),
    (CANCELLATION, ["cancel my order", "cancel the order", "cancel order", "want to cancel"]),
    (ORDER_STATUS, [
        "where is my order", "where's my order", "track my order", "track order",
        "order status", "status of my order", "my order", "is my order ready",
        "when will my order", "my delivery", "my laundry ready",
    ]),
    (SPECIAL_ITEM, [
        "wedding dress", "wedding gown", "leather", "suede", "handbag", "fur ",
        "carpet", "curtain", "saddle", "biohazard", "hazardous",
    ]),
    (NEW_ORDER, [
        "arrange a pickup", "arrange pickup", "book a pickup", "schedule a pickup",
        "schedule pickup", "collect my", "pick up my", "pickup my", "want a pickup",
        "laundry pickup", "place an order", "new order", "want to order", "book laundry",
        "i want to arrange",
    ]),
    (PICKUP_DELIVERY, [
        "do you deliver", "delivery charge", "delivery fee", "pickup charge",
        "free delivery", "which areas", "do you cover", "service area", "areas you cover",
        "delivery time", "how long does delivery",
    ]),
    (PRICE, ["price", "cost", "how much", "rate", "charge for", "charges for", "quote"]),
    (SERVICE, [
        "what services", "services do you", "do you do", "do you clean", "do you wash",
        "can you clean", "can you wash", "what do you offer", "dry clean", "wash and fold",
        "wash and iron", "ironing",
    ]),
]


def classify(text: str) -> str:
    """Return the best intent for a message in isolation (no conversation context).
    Returns UNKNOWN for short contextual follow-ups the caller must resolve from state.
    """
    if not text or not text.strip():
        return UNKNOWN
    if _GREETING.match(text):
        return GREETING
    lowered = f" {text.lower().strip()} "
    for intent, keywords in _ORDERED_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return intent
    return UNKNOWN
