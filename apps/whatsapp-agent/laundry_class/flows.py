"""Pure helpers used by the graph turn: contextual intent resolution, order-slot
merging, price estimation, and answering recall/"what did I say" questions. Kept
out of graph.py so the node stays readable and each piece is unit-testable.
"""
from __future__ import annotations

import re

from laundry_class import intents as I
from laundry_class import knowledge_base as kb
from laundry_class import slots

# service label -> the "Service" column value to filter the price table on
_SERVICE_FILTER = {
    "Wash and Iron": "Wash and Press",
    "Ironing Only": "Ironing Only",
    "Dry Cleaning": "Dry Cleaning",
    "Wash and Fold": "Wash and Fold",
}

# Leading-word match so "yes, confirm." / "sure, go ahead" also count.
_AFFIRM = re.compile(r"^\s*(yes+|yeah+|yep+|yup+|sure|ok(ay)?|confirm(ed)?|go ahead|"
                     r"correct|that'?s right|please do|sounds good)\b", re.IGNORECASE)
_NEGATIVE = re.compile(r"^\s*(no+|nope|not now|not yet|cancel that|don'?t|no thanks)\b", re.IGNORECASE)

_RECALL_SUBSTRINGS = (
    "did i give", "did i choose", "did i say", "did i tell", "did i send", "did i pick",
    "did i select", "did i request", "did i book", "i gave you", "i chose", "i told you",
    "do you have for me",
    "have for me", "what did i", "what time did i", "what address", "which address",
    "what name", "how much do i", "need to pay", "what do i owe", "on file",
    "what time is my", "when is my pickup", "my pickup time", "time is my pickup",
)


def is_recall_question(text: str) -> bool:
    lowered = text.lower()
    return any(sub in lowered for sub in _RECALL_SUBSTRINGS)


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRM.match(text))


def is_negative(text: str) -> bool:
    return bool(_NEGATIVE.match(text))


# ---------------------------------------------------------------------------
# Contextual intent resolution
# ---------------------------------------------------------------------------
def resolve_intent(text: str, *, last_agent_action: str | None, prior_intent: str | None,
                   order_in_progress: bool, has_active_order: bool) -> str:
    """Combine the isolated-message classifier with conversation context so short
    follow-ups ("yes", "at 6", "same address", "and a shirt?") route correctly."""
    base = I.classify(text)
    laa = last_agent_action or ""

    # While an order is being collected, price/service/pickup/vague messages are
    # answers to the collection, not fresh top-level intents — so we don't drop
    # out of the flow (e.g. giving the service mid-order must not become a service
    # enquiry). Strong intents (refund/damage/status/human/cancel/reschedule) still
    # interrupt.
    _CONTINUE_ORDER = {I.PRICE, I.SERVICE, I.PICKUP_DELIVERY, I.NEW_ORDER, I.UNKNOWN}
    if order_in_progress and base in _CONTINUE_ORDER:
        return I.NEW_ORDER

    if base != I.UNKNOWN:
        return base

    # base == UNKNOWN: resolve from context.
    if laa.startswith("reschedule"):
        return I.DELIVERY_RESCHEDULE
    if laa.startswith("handoff") or laa.startswith("human_ack"):
        return prior_intent or I.HUMAN_SUPPORT
    if laa == "price":
        return I.PRICE  # "and a shirt?", "what's the total?"
    if laa == "special_item":
        return I.SPECIAL_ITEM  # follow-ups about an unlisted/inspection item stay in context
    if laa == "order_status":
        return I.ORDER_STATUS
    if laa.startswith("order") or order_in_progress:
        return I.NEW_ORDER
    if has_active_order:
        return I.ORDER_STATUS
    # A bare item list with nothing else in context starts an order.
    if slots.extract_items(text):
        return I.NEW_ORDER
    return I.UNKNOWN


# ---------------------------------------------------------------------------
# Slot merge
# ---------------------------------------------------------------------------
def extract_delta(text: str, *, expecting_time: bool, expecting_items: bool) -> dict:
    """Everything we can newly learn from this message, as an order-details delta."""
    delta: dict = {}
    if (name := slots.extract_name(text)):
        delta["customer_name"] = name
    if (area := slots.extract_area(text)):
        delta["area"] = area
    if (service := slots.extract_service(text)):
        delta["service"] = service
    if (payment := slots.extract_payment(text)):
        delta["payment_method"] = payment
    if (t := slots.extract_time(text, expecting_time=expecting_time)):
        delta["pickup_time"] = t
    if (addr := slots.extract_address(text)):
        delta["address"] = addr
    items = slots.extract_items(text)
    if items:
        delta["items"] = items
    return delta


def merge_items(existing: list | None, new: list | None) -> list:
    """Append newly-mentioned items to any already collected."""
    return (existing or []) + (new or [])


# ---------------------------------------------------------------------------
# Estimation (never invents; unlisted items are flagged, not priced)
# ---------------------------------------------------------------------------
def estimate(details: dict) -> dict:
    """Return {lines, subtotal, has_unpriced, unpriced_items, items_text}."""
    service = details.get("service")
    svc_filter = _SERVICE_FILTER.get(service) if service else None
    lines = []
    subtotal = 0.0
    unpriced = []
    labels = []
    for it in details.get("items", []):
        qty = it.get("quantity", 1)
        raw = it.get("raw") or it.get("item")
        entry = kb.find_price(raw, svc_filter) or kb.find_price(raw)
        label = f"{qty} {it.get('item', raw)}"
        labels.append(label)
        if entry and not entry.inspection_required:
            line_total = qty * entry.price_aed
            subtotal += line_total
            note = "" if svc_filter and svc_filter.lower() in entry.service.lower() \
                else f" ({entry.service.lower()})"
            lines.append({"label": label + note, "line_total": line_total})
        else:
            unpriced.append(it.get("item", raw))
    return {
        "lines": lines,
        "subtotal": subtotal if lines else None,
        "has_unpriced": bool(unpriced),
        "unpriced_items": unpriced,
        "items_text": ", ".join(labels) if labels else None,
    }


# ---------------------------------------------------------------------------
# Recall / "what did I say" answers
# ---------------------------------------------------------------------------
def answer_recall_from_order(order: dict, text: str) -> str | None:
    lowered = text.lower()
    if any(k in lowered for k in ("what did i send", "what items", "which items", "what did i give you to")):
        items = ", ".join(f"{i['quantity']} × {i['item']}" for i in order.get("items", []))
        return f"Your order {order['order_id']} ({order.get('service')}) has: {items}."
    if any(k in lowered for k in ("how much", "pay", "total", "cost")):
        return (
            f"The estimated total for {order['order_id']} is AED {order.get('estimated_total_aed')}. "
            f"Payment method: {order.get('payment_method')}."
        )
    if "address" in lowered or ("where" in lowered and "come" in lowered):
        return f"Delivery/pickup address on file: {order.get('address')}."
    if "time" in lowered or "when" in lowered:
        if order.get("delivery_window"):
            return f"Your delivery window for {order['order_id']} is {order['delivery_window']} (estimated)."
        return f"Pickup time on file: {order.get('pickup_time')}."
    return None


def answer_recall_from_details(details: dict, text: str) -> str | None:
    lowered = text.lower()
    if "address" in lowered:
        addr = details.get("address")
        if addr:
            return f"The address you gave me is: {addr}."
        if details.get("area"):
            return f"The pickup area you gave me is {details['area']}."
        return None
    if "time" in lowered or "when" in lowered or "pickup" in lowered:
        t = details.get("pickup_time")
        if not t:
            return None
        return f"Your pickup is set for {t}." if "at" in str(t) else f"You requested pickup at {t}."
    if "name" in lowered:
        n = details.get("customer_name")
        return f"You told me your name is {n}." if n else None
    if any(k in lowered for k in ("what did i", "items", "send")):
        items = details.get("items")
        if items:
            return "You mentioned: " + ", ".join(f"{i['quantity']} × {i['item']}" for i in items) + "."
    return None
