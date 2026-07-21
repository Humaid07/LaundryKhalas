"""LangGraph conversation state for the Laundry Class agent.

`messages` uses LangGraph's `add_messages` reducer so each turn *appends* to the
running history instead of replacing it (task Part 4, Step 4). `collected_order_details`
uses a merge reducer so a detail given three turns ago is never lost when the next
turn only adds one new field.

Nothing sensitive is stored: no passwords, card numbers, OTPs, or PII beyond the
phone number needed to key the conversation and look up a dummy order.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


def merge_dict(left: dict | None, right: dict | None) -> dict:
    """Reducer: shallow-merge order details across turns, newest value wins.
    A `None` value in `right` clears the key (used to reset on a fresh order)."""
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def take_last(_left: Any, right: Any) -> Any:
    """Reducer: overwrite with the latest value (default dict-merge would be wrong
    for scalar fields that legitimately change each turn)."""
    return right


class ConversationState(TypedDict, total=False):
    # Running transcript (appended to via add_messages).
    messages: Annotated[list, add_messages]

    # Identity / threading.
    phone_number: Annotated[str, take_last]
    thread_id: Annotated[str, take_last]
    customer_name: Annotated[str | None, take_last]

    # Routing / this-turn analysis.
    detected_intent: Annotated[str, take_last]
    current_order_id: Annotated[str | None, take_last]

    # Order collection (merged across turns).
    collected_order_details: Annotated[dict, merge_dict]
    missing_order_fields: Annotated[list[str], take_last]

    # Human handoff.
    handoff_required: Annotated[bool, take_last]
    handoff_reason: Annotated[str | None, take_last]
    handoff_status: Annotated[str | None, take_last]  # pending | assigned | resolved
    handoff_notified: Annotated[bool, take_last]      # guards against duplicate notifications

    # Bookkeeping.
    last_agent_action: Annotated[str | None, take_last]
    conversation_summary: Annotated[str, take_last]
    last_updated_at: Annotated[str, take_last]
    fallback_streak: Annotated[int, take_last]


# Fields a testing order must have before it can be summarised/confirmed. The
# customer's name is requested at the start of an explicit booking but is not a
# hard blocker (some customers jump straight to items), so it is not listed here.
MANDATORY_ORDER_FIELDS = ["service", "items", "area", "pickup_time", "payment_method"]
