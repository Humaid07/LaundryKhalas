"""Stateful order flows: the layer that makes the conversation *do something*
to a real, queryable order row instead of only producing chat text.

For the order intents (book pickup, track, cancel, change pickup time, add
items) this module reads/writes the order store (services/order_store.py)
and returns a deterministic, demo-honest reply. Booking builds up a draft
order slot-by-slot across turns and, on confirmation, flips it to an active
mock order that then shows up in the dashboard's active list. Track/cancel/
change/add read and mutate the stored order (dummy IDs LK-AE-1024..1027 or a
just-created one) - never inventing an order, never claiming a real action.

Returning None means "this turn isn't an order-flow turn" - the agent then
falls back to the normal LLM(mock) reply path (greeting/pricing/small talk).

Every reply here is mock/demo. Nothing contacts a live order, driver,
payment or support system.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agents.whatsapp_agent import tools
from agents.whatsapp_agent.actions import CONFIRM_ACTIONS, SERVICE_ACTIONS, Action
from rules import mock_tags, service_labels
from services import order_store

_TAGS = mock_tags()
_ORDER_TAG = _TAGS["order_tag"]

# Markers left in the agent's own questions so a bare follow-up ("LK-AE-1024",
# "2 suits", "yes") routes back into the right flow with no extra state.
_BOOKING_SUMMARY_MARKER = "please review and confirm"

_ORDER_FLOW_INTENTS = {
    "track_order_request",
    "cancel_order_request",
    "change_pickup_time_request",
}
_BOOKING_INTENTS = {"new_pickup_request", "service_question", "area_question"}
_BOOKING_MAYBE_INTENTS = {"confirmation_yes", "confirmation_no", "unknown_laundry_related"}
_HARD_RESET_INTENTS = (
    {"greeting", "smalltalk_thanks", "smalltalk_farewell", "confirmation_no"}
    | _ORDER_FLOW_INTENTS
    | {"add_items_request", "call_support_request"}
)

_NOT_FOUND = (
    "I couldn't find that order ID in demo data. Please check the ID or "
    "connect with our support team."
)


@dataclass
class OrderOutcome:
    text: str
    intent: str
    actions: list[Action] = field(default_factory=list)
    order_id: str | None = None
    order_status: str | None = None


def _pickup_line(order) -> str:
    parts = [p for p in (order.pickup_date, order.pickup_time) if p]
    return f" Pickup is set for {' '.join(parts)}." if parts else ""


def _items_text(order) -> str:
    return ", ".join(order.items) if order.items else "to be confirmed"


async def handle(
    db,
    conversation,
    *,
    intent: str,
    action_id: str | None,
    text: str,
    history: list[tuple[str, str]],
) -> OrderOutcome | None:
    # Booking confirm/cancel buttons carry their own meaning regardless of the
    # label text the UI sent alongside them.
    if action_id == "confirm_booking":
        intent = "confirmation_yes"
    elif action_id == "cancel_booking":
        intent = "confirmation_no"

    # 1. Cancellation confirmation ("...send a cancellation request?") - must be
    #    checked before booking so a "yes" here cancels rather than books.
    if tools.last_agent_asked(history, tools.CANCEL_CONFIRM_MARKER):
        return await _handle_cancel_confirm(db, intent, text, history)

    # 2. A pending track/cancel/change/add follow-up (bare order id / items)
    #    resolves back to the flow it answers.
    pending = tools.pending_order_action(history)
    effective = intent
    if pending and intent not in _HARD_RESET_INTENTS:
        effective = pending

    if effective in _ORDER_FLOW_INTENTS:
        return await _handle_track_cancel_change(db, effective, intent, text)

    if effective == "add_items_request":
        # Ask turn: the customer just requested to add items (button/keyword).
        # Answer turn: pending routing made it effective but the raw intent is
        # something else - the message itself is the item list.
        is_followup = intent != "add_items_request"
        return await _handle_add_items(db, conversation, intent, text, is_followup=is_followup)

    # 3. Booking flow (draft order built up + activated on confirm).
    if _is_booking_turn(effective, history, text, db_draft_exists=False):
        return await _handle_booking(db, conversation, effective, text, history)

    return None


# ---------------------------------------------------------------------------
# Track / cancel / change pickup time
# ---------------------------------------------------------------------------
async def _handle_track_cancel_change(db, effective: str, intent: str, text: str) -> OrderOutcome:
    order_id = tools.extract_order_id(text)

    if not order_id:
        if effective == "track_order_request":
            msg = (
                "Sure. Please share your LaundryKhalaas order ID so I can help "
                "you check the status." + _ORDER_TAG
            )
        elif effective == "cancel_order_request":
            msg = (
                "Sure. Please share your order ID. Our team will confirm "
                "whether the order can still be cancelled." + _ORDER_TAG
            )
        else:  # change_pickup_time_request
            msg = (
                "Please share your order ID and the new pickup time you prefer. "
                "Our team will confirm availability." + _ORDER_TAG
            )
        return OrderOutcome(text=msg, intent=intent)

    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        return OrderOutcome(text=_NOT_FOUND, intent=intent)

    label = order_store.status_label(order.status)

    if effective == "track_order_request":
        msg = (
            f"Your order {order.order_id} is currently {label}.{_pickup_line(order)} "
            "Demo mode — this is mock tracking data."
        )
        return OrderOutcome(
            text=msg, intent=intent, order_id=order.order_id, order_status=order.status
        )

    if effective == "cancel_order_request":
        if order.status == order_store.COMPLETED:
            msg = (
                f"Order {order.order_id} is already completed, so it can't be "
                "cancelled from the chat. I can connect you with support if you "
                "need help."
            )
            return OrderOutcome(
                text=msg, intent=intent, order_id=order.order_id, order_status=order.status
            )
        # Never cancels here - asks for explicit confirmation first.
        msg = (
            f"Order {order.order_id} is currently {label}. Do you want me to send "
            "a cancellation request to the support team?" + _ORDER_TAG
        )
        return OrderOutcome(
            text=msg, intent=intent, order_id=order.order_id, order_status=order.status
        )

    # change_pickup_time_request
    new_time = tools.extract_time_hint(text)
    if not new_time:
        msg = (
            f"Thanks. Please share the new pickup time you prefer for order "
            f"{order.order_id}." + _ORDER_TAG
        )
        return OrderOutcome(
            text=msg, intent=intent, order_id=order.order_id, order_status=order.status
        )
    await order_store.request_pickup_change(db, order, new_time)
    await db.commit()
    msg = (
        f"Noted. I've added your pickup time change request for order "
        f"{order.order_id} (new time: {new_time}). The team will confirm "
        "availability. Demo mode — this is not yet connected to live operations."
    )
    return OrderOutcome(
        text=msg, intent=intent, order_id=order.order_id, order_status=order.status
    )


async def _handle_cancel_confirm(
    db, intent: str, text: str, history: list[tuple[str, str]]
) -> OrderOutcome:
    # Which order was the confirmation about? The id is in the agent's question.
    prev_text = history[-1][1] if history else ""
    order_id = tools.extract_order_id(prev_text)
    order = await order_store.find_order_by_id(db, order_id) if order_id else None

    # Accept the confirmation from the intent OR the raw text ("yes please",
    # "go ahead") - and never treat a negative as a yes.
    lowered = text.strip().lower()
    leads_yes = lowered.startswith(
        ("yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "go ahead", "please")
    )
    said_yes = (
        intent == "confirmation_yes" or tools.is_affirmative(text) or leads_yes
    ) and not tools.is_negative(text)

    if not said_yes:
        # Treated as "no" / anything non-affirmative -> do not cancel.
        return OrderOutcome(
            text="No problem — I won't request a cancellation. Let us know if you "
            "need anything else.",
            intent=intent,
            order_id=order.order_id if order else None,
            order_status=order.status if order else None,
        )

    if order is not None and order.status != order_store.COMPLETED:
        await order_store.request_cancellation(db, order)
        await db.commit()
    msg = (
        "Your cancellation request has been noted. The LaundryKhalaas team will "
        "confirm whether it can still be cancelled. Demo mode — no live "
        "cancellation has been made."
    )
    return OrderOutcome(
        text=msg,
        intent=intent,
        order_id=order.order_id if order else None,
        order_status=order.status if order else None,
    )


# ---------------------------------------------------------------------------
# Add more items
# ---------------------------------------------------------------------------
async def _handle_add_items(
    db, conversation, intent: str, text: str, *, is_followup: bool
) -> OrderOutcome:
    # Ask turn: the customer's message is the request itself -> ask what to add.
    # Answer turn: the message carries the actual items.
    if not is_followup:
        return OrderOutcome(
            text="Sure. Please tell me what items you would like to add to your "
            "laundry order.",
            intent=intent,
        )

    items = text.strip()
    order_id = tools.extract_order_id(items)
    order = None
    if order_id:
        order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        order = await order_store.latest_order_for_conversation(db, conversation.id)

    if order is not None:
        await order_store.add_order_items(db, order, items)
        await db.commit()
        return OrderOutcome(
            text=f"Got it. I've added this to your request: {items}. The final "
            "price will be confirmed by the team." + _ORDER_TAG,
            intent=intent,
            order_id=order.order_id,
            order_status=order.status,
        )
    return OrderOutcome(
        text=f"Got it. I've noted these items: {items}. The final price will be "
        "confirmed by the team." + _ORDER_TAG,
        intent=intent,
    )


# ---------------------------------------------------------------------------
# Booking flow
# ---------------------------------------------------------------------------
def _is_booking_turn(effective: str, history, text, *, db_draft_exists: bool) -> bool:
    if effective in _BOOKING_INTENTS:
        return True
    if tools.last_agent_asked(history, tools.BOOKING_ITEMS_MARKER):
        return True
    if tools.last_agent_asked(history, _BOOKING_SUMMARY_MARKER):
        return True
    if effective in _BOOKING_MAYBE_INTENTS:
        slots = tools.accumulate_slots(history, text)
        if slots["service_type"] or slots["area"] or slots["time_hint"]:
            return True
    return False


async def _handle_booking(db, conversation, effective: str, text, history) -> OrderOutcome:
    slots = tools.accumulate_slots(history, text)
    service = slots["service_type"]
    area = slots["area"]
    time_hint = slots["time_hint"]

    # Capture item details when this turn answers the item-details question.
    captured_items = None
    if tools.last_agent_asked(history, tools.BOOKING_ITEMS_MARKER) and text.strip():
        captured_items = text.strip()

    # Upsert a draft order so the conversation state persists behind the scenes.
    draft = await order_store.get_draft_for_conversation(db, conversation.id)
    if draft is None and service:
        draft = await order_store.create_order(
            db,
            order_id=await order_store.next_order_id(db),
            conversation_id=conversation.id,
            status=order_store.DRAFT,
            source_channel=conversation.channel or "whatsapp",
            customer_name=conversation.customer_name,
            customer_phone=conversation.customer_phone,
        )

    if draft is not None:
        updates: dict = {}
        if service:
            updates["service_type"] = service_labels().get(service, service)
        if area:
            updates["pickup_area"] = area
        if time_hint:
            updates["pickup_time"] = time_hint
        if captured_items:
            updates["items"] = [captured_items]
        if conversation.customer_name and not draft.customer_name:
            updates["customer_name"] = conversation.customer_name
        if conversation.customer_phone and not draft.customer_phone:
            updates["customer_phone"] = conversation.customer_phone
        if updates:
            await order_store.update_order(db, draft, **updates)

    items_known = bool(draft and draft.items)

    # Ordered slot collection: service -> items -> area -> time -> confirm.
    if not service:
        await db.commit()
        return OrderOutcome(
            text="Great. Which service do you need today?",
            intent="new_pickup_request",
            actions=SERVICE_ACTIONS,
        )

    service_label = service_labels().get(service, service)

    if not items_known:
        await db.commit()
        return OrderOutcome(
            text=f"Perfect. Please share the item details for your {service_label} "
            "(for example: 2 shirts, 1 suit).",
            intent="new_pickup_request",
            order_id=draft.order_id if draft else None,
            order_status=draft.status if draft else None,
        )

    if not area:
        await db.commit()
        return OrderOutcome(
            text="Great. Please share your pickup area or address.",
            intent="new_pickup_request",
            order_id=draft.order_id if draft else None,
            order_status=draft.status if draft else None,
        )

    if not time_hint:
        await db.commit()
        return OrderOutcome(
            text="Almost done — what day or time works for pickup?",
            intent="new_pickup_request",
            order_id=draft.order_id if draft else None,
            order_status=draft.status if draft else None,
        )

    # All details present.
    if effective == "confirmation_no":
        await db.commit()
        return OrderOutcome(
            text="No problem! Your booking isn't confirmed. Let us know if you'd "
            "like to continue or need anything else.",
            intent="confirmation_no",
            order_id=draft.order_id if draft else None,
            order_status=draft.status if draft else None,
        )

    if effective == "confirmation_yes" and draft is not None:
        await order_store.update_order(db, draft, status=order_store.ACTIVE)
        await db.commit()
        summary = (
            "Your mock booking request has been created.\n\n"
            f"Order ID: {draft.order_id}\n"
            f"Service: {draft.service_type}\n"
            f"Items: {_items_text(draft)}\n"
            f"Pickup Area: {draft.pickup_area}\n"
            f"Pickup Time: {draft.pickup_time}\n"
            "Status: Active\n\n"
            "Demo mode — this is a mock order for testing."
        )
        return OrderOutcome(
            text=summary,
            intent="confirmation_yes",
            order_id=draft.order_id,
            order_status=order_store.ACTIVE,
        )

    # Everything collected but not yet confirmed -> show summary + confirm.
    await db.commit()
    summary = (
        "Here's your booking so far:\n"
        f"Service: {service_label}\n"
        f"Items: {_items_text(draft) if draft else 'to be confirmed'}\n"
        f"Pickup Area: {area}\n"
        f"Pickup Time: {time_hint}\n\n"
        f"Please review and confirm to create your mock booking.{_ORDER_TAG}"
    )
    return OrderOutcome(
        text=summary,
        intent="new_pickup_request",
        actions=CONFIRM_ACTIONS,
        order_id=draft.order_id if draft else None,
        order_status=draft.status if draft else None,
    )
