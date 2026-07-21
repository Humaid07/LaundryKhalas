"""The LangGraph state machine for the Laundry Class agent.

Graph: START -> agent_turn -> handoff_notify -> END, with a persistent SQLite
checkpointer keyed by thread_id = "whatsapp:<phone>". The checkpointer is what
gives each WhatsApp number its own isolated, restart-surviving short-term memory.

`agent_turn` classifies the message in context, updates order slots (merged across
turns), retrieves the relevant KB section, prices from the KB (never inventing),
decides on handoff, builds a directive, and calls the LangChain chat model for the
reply text. `handoff_notify` sends the structured admin notification exactly once
per case.
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from laundry_class import flows
from laundry_class import handoff as ho
from laundry_class import intents as I
from laundry_class import knowledge_base as kb
from laundry_class import observability as obs
from laundry_class.responder import build_chat_model, compose, directive_message
from laundry_class.state import MANDATORY_ORDER_FIELDS, ConversationState

_MODEL = build_chat_model()

_THANKS = re.compile(r"^\s*(thanks|thank you|thankyou|thx|ty|shukran|appreciate it)[\s!.,]*$", re.IGNORECASE)
_FAREWELL = re.compile(r"^\s*(bye|goodbye|see you|take care|good night)[\s!.,]*$", re.IGNORECASE)
_THIRD_PARTY = re.compile(r"\b([A-Z][a-z]+)'s (order|address|laundry|delivery|details)\b")
_COLLECT_REQUEST = re.compile(r"\b(collect|pick ?up|come today|today|schedule|book)\b", re.IGNORECASE)

# Order-building slots — only persisted to memory on a new_order turn.
_ORDER_SLOT_KEYS = {
    "customer_name", "area", "service", "payment_method", "pickup_time", "address",
    "items", "express", "_confirmed", "_order_ref",
}


def _last_human_text(state: ConversationState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _dummy_ref() -> str:
    return f"LC-TEST-{random.randint(9000, 9999)}"


def _next_missing(details: dict) -> str | None:
    for field in MANDATORY_ORDER_FIELDS:
        val = details.get(field)
        if field == "items":
            if not val:
                return "items"
        elif field == "pickup_time":
            if not val:
                return "pickup_time"
            # present but vague (no clock digit) -> ask a narrower time first
            if not re.search(r"\d", str(val)):
                return "pickup_time_narrow"
        elif not val:
            return field
    return None


# ---------------------------------------------------------------------------
# Main turn
# ---------------------------------------------------------------------------
def agent_turn(state: ConversationState) -> dict:
    text = _last_human_text(state)
    phone = state.get("phone_number", "")
    details = dict(state.get("collected_order_details") or {})
    laa = state.get("last_agent_action")
    prior_intent = state.get("detected_intent")
    fallback_streak = state.get("fallback_streak", 0)
    is_first_turn = len([m for m in state.get("messages", []) if isinstance(m, HumanMessage)]) <= 1

    order_confirmed = bool(details.get("_confirmed"))
    order_in_progress = (
        any(details.get(k) for k in ("service", "items", "area", "pickup_time"))
        and not order_confirmed
    )
    active_order = kb.find_order_by_phone(phone)

    # --- classify -----------------------------------------------------------
    if _THANKS.match(text):
        intent = "smalltalk_thanks"
    elif _FAREWELL.match(text):
        intent = "smalltalk_farewell"
    else:
        intent = flows.resolve_intent(
            text,
            last_agent_action=laa,
            prior_intent=prior_intent,
            order_in_progress=order_in_progress,
            has_active_order=active_order is not None,
        )

    expecting_time = laa in ("order_ask:pickup_time", "order_ask:pickup_time_narrow", "reschedule_ask")
    delta = flows.extract_delta(text, expecting_time=expecting_time, expecting_items=(laa == "order_ask:items"))
    if delta.get("items"):
        delta["items"] = flows.merge_items(details.get("items"), delta["items"])
    new_details = {**details, **delta}

    ctx = _TurnCtx(
        text=text, phone=phone, intent=intent, laa=laa, is_first_turn=is_first_turn,
        details=new_details, delta=delta, active_order=active_order, fallback_streak=fallback_streak,
    )
    result = _dispatch(ctx)

    # Order slots are only ever committed to memory while the order-building flow is
    # active. This stops a complaint like "my dress has a tear" (which superficially
    # contains "a tear") from polluting the order state on a non-order turn.
    if intent != I.NEW_ORDER:
        result.details_delta = {
            k: v for k, v in result.details_delta.items() if k not in _ORDER_SLOT_KEYS
        }

    # --- assemble state update ---------------------------------------------
    # Route the composed directive through the LangChain chat model so the same
    # graph edge works for a live provider too (the deterministic model returns
    # exactly `compose(directive)`). `raw` results carry their own final text.
    if result.text is not None:
        ai_text = result.text
    else:
        ai_text = _MODEL.invoke(
            [directive_message(result.directive["kind"], **result.directive["payload"])]
        ).content

    updates: dict = {
        "messages": [AIMessage(content=ai_text)],
        "detected_intent": intent,
        "last_agent_action": result.last_agent_action,
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "phone_number": phone,
        "collected_order_details": result.details_delta,
        "missing_order_fields": _missing_list(result.details_full),
        "fallback_streak": result.fallback_streak,
    }
    if result.customer_name is not None:
        updates["customer_name"] = result.customer_name
    if result.current_order_id is not None:
        updates["current_order_id"] = result.current_order_id
    if result.handoff_required:
        updates["handoff_required"] = True
        updates["handoff_reason"] = result.handoff_reason
        if state.get("handoff_status") in (None, ho.RESOLVED):
            updates["handoff_status"] = ho.PENDING

    # --- masked structured log ---------------------------------------------
    section_title, _ = kb.retrieve(intent, text)
    obs.log_turn({
        "phone_number": phone,
        "thread_id": state.get("thread_id"),
        "detected_intent": intent,
        "kb_section": section_title,
        "current_order_id": updates.get("current_order_id") or state.get("current_order_id"),
        "memory_loaded": not is_first_turn,
        "handoff_triggered": result.handoff_required,
        "handoff_reason": result.handoff_reason,
        "response_status": "ok",
        "error": None,
    })
    return updates


def _missing_list(details: dict) -> list[str]:
    return [f for f in MANDATORY_ORDER_FIELDS
            if (not details.get(f)) or (f == "items" and not details.get("items"))]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
class _TurnCtx:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Result:
    def __init__(self, directive=None, text=None, last_agent_action=None, details_delta=None,
                 details_full=None, customer_name=None, current_order_id=None,
                 handoff_required=False, handoff_reason=None, fallback_streak=0):
        self.directive = directive or {"kind": "unknown", "payload": {}}
        self.text = text
        self.last_agent_action = last_agent_action
        self.details_delta = details_delta or {}
        self.details_full = details_full or {}
        self.customer_name = customer_name
        self.current_order_id = current_order_id
        self.handoff_required = handoff_required
        self.handoff_reason = handoff_reason
        self.fallback_streak = fallback_streak


def _d(kind, **payload):
    return {"kind": kind, "payload": payload}


def _dispatch(c: _TurnCtx) -> _Result:
    # Global privacy guard (task Part 7): never expose a third party's order or
    # details, even if the customer asks about someone by name.
    tp = _THIRD_PARTY.search(c.text)
    if tp:
        current = c.details.get("customer_name") or (c.active_order.get("customer_name") if c.active_order else None)
        current_first = current.split()[0].lower() if current else None
        if current_first != tp.group(1).lower():
            return _Result(_d("raw", text="I'm sorry, I can't share another customer's information. "
                              "I can only help with the account linked to this number."),
                           last_agent_action="privacy_refuse", details_delta=c.delta, details_full=c.details)

    # Recall / "what did I say" questions are answered from this thread's own
    # memory only — another number's thread can never satisfy them.
    if flows.is_recall_question(c.text):
        return _handle_recall(c)

    i = c.intent
    if i == "smalltalk_thanks":
        return _Result(_d("smalltalk_thanks"), last_agent_action="smalltalk",
                       details_delta=c.delta, details_full=c.details)
    if i == "smalltalk_farewell":
        return _Result(_d("smalltalk_farewell"), last_agent_action="smalltalk",
                       details_delta=c.delta, details_full=c.details)
    if i == I.GREETING:
        return _Result(_d("greeting", name=c.details.get("customer_name"),
                          returning=not c.is_first_turn),
                       last_agent_action="greeting", details_delta=c.delta, details_full=c.details)
    if i == I.PRICE:
        return _handle_price(c)
    if i == I.SERVICE:
        return _Result(_d("service_info"), last_agent_action="service",
                       details_delta=c.delta, details_full=c.details)
    if i == I.PICKUP_DELIVERY:
        return _Result(_d("pickup_delivery_info"), last_agent_action="pickup_delivery",
                       details_delta=c.delta, details_full=c.details)
    if i == I.NEW_ORDER:
        return _handle_order(c)
    if i == I.ORDER_STATUS:
        return _handle_status(c)
    if i == I.DELIVERY_RESCHEDULE:
        return _handle_reschedule(c)
    if i == I.CANCELLATION:
        return _handle_cancellation(c)
    if i in (I.REFUND, I.DAMAGE, I.MISSING_ITEM):
        return _handle_complaint(c)
    if i == I.PAYMENT:
        return _handle_payment(c)
    if i == I.SPECIAL_ITEM:
        return _handle_special_item(c)
    if i == I.HUMAN_SUPPORT:
        return _handle_human(c)
    return _handle_unknown(c)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _handle_recall(c: _TurnCtx) -> _Result:
    recall = flows.answer_recall_from_details(c.details, c.text)
    if recall:
        return _Result(_d("order_recall", text=recall), last_agent_action=(c.laa or "recall"),
                       details_delta=c.delta, details_full=c.details)
    if c.active_order:
        recall = flows.answer_recall_from_order(c.active_order, c.text)
        if recall:
            return _Result(_d("order_recall", text=recall), last_agent_action="order_status",
                           details_delta=c.delta, details_full=c.details,
                           current_order_id=c.active_order["order_id"])
    return _Result(
        _d("raw", text="I don't have those details on file for this number yet. If you have an order "
           "reference, share it and I'll check — or I can help you place a new order."),
        last_agent_action=(c.laa or "recall"), details_delta=c.delta, details_full=c.details)


def _handle_price(c: _TurnCtx) -> _Result:
    from laundry_class import slots
    svc = c.delta.get("service") or c.details.get("_price_service")
    items = c.delta.get("items") or slots.extract_items(c.text)
    delta = {"_price_service": svc} if svc else {}

    wants_total = "total" in c.text.lower() or len(items) > 1 or any(i["quantity"] > 1 for i in items)

    if items and wants_total:
        est = flows.estimate({"service": svc, "items": items})
        lines = est["lines"]
        if not lines:
            return _Result(_d("price_unknown_item", item=items[0]["item"]),
                           last_agent_action="price", details_delta=delta, details_full=c.details)
        inspection_note = None
        if est["has_unpriced"]:
            inspection_note = (
                f"For {', '.join(est['unpriced_items'])}, the final price needs inspection, "
                "so it isn't included above."
            )
        return _Result(
            _d("price_multi", lines=lines, subtotal=est["subtotal"], free_delivery=True,
               area_prompt=True, inspection_note=inspection_note),
            last_agent_action="price", details_delta=delta, details_full=c.details,
        )

    if items:
        item = items[0]
        entry = kb.find_price(item["raw"], svc) or kb.find_price(item["raw"])
        if entry is None:
            return _Result(_d("price_unknown_item", item=item["item"]),
                           last_agent_action="price", details_delta=delta, details_full=c.details)
        if entry.inspection_required:
            return _Result(_d("price_single", item=entry.item, service=entry.service,
                              price=0, unit=entry.unit, inspection=True),
                           last_agent_action="price",
                           details_delta={"_price_service": entry.service}, details_full=c.details)
        note = "" if (svc and svc.lower() in entry.service.lower()) else f" ({entry.service.lower()})"
        return _Result(
            _d("price_single", item=entry.item + note, service=entry.service if not note else "",
               price=entry.price_aed, unit=entry.unit, offer_pickup=True),
            last_agent_action="price",
            details_delta={"_price_service": entry.service}, details_full=c.details,
        )

    # price question with no identifiable item -> ask which item
    return _Result(_d("clarify", question="Which item would you like the price for? "
                      "Prices are in AED."),
                   last_agent_action="price", details_delta=delta, details_full=c.details)


def _handle_order(c: _TurnCtx) -> _Result:
    details = dict(c.details)
    text_l = c.text.lower()

    # express mention: never invent a surcharge (KB pricing rule 8)
    express_note = None
    if "express" in text_l or "same day" in text_l or "same-day" in text_l:
        details["express"] = True
        express_note = ("Express/same-day service is available on request, but the price and "
                        "timing must be confirmed by our team — I can't quote an express surcharge myself.")

    all_present = all(details.get(f) for f in MANDATORY_ORDER_FIELDS if f != "items") and details.get("items")
    time_vague = details.get("pickup_time") and not re.search(r"\d", str(details["pickup_time"]))

    # confirmation
    if all_present and not time_vague and c.laa == "order_summary":
        if flows.is_negative(c.text):
            d = {**c.delta}
            return _Result(_d("raw", text="No problem — your booking isn't confirmed. "
                              "Let me know if you'd like to continue."),
                           last_agent_action="order_cancelled", details_delta=d, details_full=details)
        if flows.is_affirmative(c.text):
            ref = details.get("_order_ref") or _dummy_ref()
            est = flows.estimate(details)
            d = {**c.delta, "_confirmed": True, "_order_ref": ref}
            return _Result(
                _d("order_confirmed", details=details, order_ref=ref,
                   items_text=est["items_text"], subtotal=est["subtotal"]),
                last_agent_action="order_confirmed", details_delta=d, details_full=details,
                current_order_id=ref, customer_name=details.get("customer_name"),
            )

    # fresh explicit start with nothing known -> ask name + area together
    started_empty = (
        I.classify(c.text) == I.NEW_ORDER
        and not any(details.get(k) for k in ("service", "items", "area", "customer_name"))
    )
    if started_empty:
        return _Result(_d("order_ask", missing_field="customer_name_area", known=details),
                       last_agent_action="order_ask:customer_name_area",
                       details_delta=c.delta, details_full=details,
                       customer_name=details.get("customer_name"))

    missing = _next_missing(details)
    est = flows.estimate(details)
    estimate_line = None
    if details.get("items") and est["subtotal"] is not None:
        from laundry_class.responder import _money
        estimate_line = f"Estimated subtotal so far: {_money(est['subtotal'])} (estimate)."

    if missing:
        payload = {"missing_field": missing, "known": details}
        if estimate_line and missing in ("area", "pickup_time", "payment_method"):
            payload["estimate_line"] = estimate_line
        directive = _d("order_ask", **payload)
        # inject express note if present
        if express_note:
            directive = _d("raw", text=_compose_with_note(directive, express_note))
        return _Result(directive, last_agent_action=f"order_ask:{missing}",
                       details_delta={**c.delta, **_persist_flags(details)},
                       details_full=details, customer_name=details.get("customer_name"))

    # all present -> summary
    ref = details.get("_order_ref") or _dummy_ref()
    d = {**c.delta, "_order_ref": ref, **_persist_flags(details)}
    directive = _d("order_summary", details=details, items_text=est["items_text"], subtotal=est["subtotal"])
    if express_note:
        directive = _d("raw", text=_compose_with_note(directive, express_note))
    return _Result(directive, last_agent_action="order_summary", details_delta=d,
                   details_full=details, customer_name=details.get("customer_name"),
                   current_order_id=ref)


def _persist_flags(details: dict) -> dict:
    out = {}
    if details.get("express"):
        out["express"] = True
    return out


def _compose_with_note(directive: dict, note: str) -> str:
    return f"{note}\n\n{compose(directive)}"


def _handle_status(c: _TurnCtx) -> _Result:
    # recall from an in-progress order first, then the dummy order for this phone
    recall = flows.answer_recall_from_details(c.details, c.text)
    if recall:
        return _Result(_d("order_recall", text=recall), last_agent_action="order_status",
                       details_delta=c.delta, details_full=c.details)

    order = c.active_order
    # third-party privacy: asking about someone else's order by name
    tp = _THIRD_PARTY.search(c.text)
    if tp and (not order or tp.group(1).lower() != (order.get("customer_name", "").split()[0].lower() if order else "")):
        return _Result(_d("raw", text="I'm sorry, I can't share another customer's information. "
                          "I can only help with the account linked to this number."),
                       last_agent_action="privacy_refuse", details_delta=c.delta, details_full=c.details)

    if order is None:
        if c.details.get("area") or c.details.get("items"):
            return _Result(_d("raw", text="I don't have a completed order on file for this number yet, "
                              "but I can help you place one or check details. What would you like?"),
                           last_agent_action="order_status", details_delta=c.delta, details_full=c.details)
        return _Result(_d("raw", text="I don't see an order linked to this number yet. If you have an "
                          "order reference, share it and I'll check, or I can help you place a new order."),
                       last_agent_action="order_status", details_delta=c.delta, details_full=c.details)

    recall = flows.answer_recall_from_order(order, c.text)
    if recall and c.laa in ("order_status",) and not I.classify(c.text) == I.ORDER_STATUS:
        return _Result(_d("order_recall", text=recall), last_agent_action="order_status",
                       details_delta=c.delta, details_full=c.details, current_order_id=order["order_id"])

    return _Result(_d("order_status", order=order), last_agent_action="order_status",
                   details_delta=c.delta, details_full=c.details,
                   current_order_id=order["order_id"], customer_name=order.get("customer_name"))


def _handle_reschedule(c: _TurnCtx) -> _Result:
    from laundry_class import slots
    order = c.active_order
    order_id = order["order_id"] if order else (slots.extract_order_id(c.text) or c.details.get("current_order_id"))
    if not order_id:
        return _Result(_d("raw", text="Sure — could you share your order reference so I can note the "
                          "new delivery time?"), last_agent_action="reschedule_ask",
                       details_delta=c.delta, details_full=c.details)

    # First reschedule turn: ask for the preferred new time rather than mistaking the
    # *current* delivery time the customer is complaining about ("coming around 4, I
    # won't be home") for their requested new time. Only the follow-up records a time.
    if c.laa != "reschedule_ask":
        return _Result(_d("reschedule_ask_time", order_id=order_id),
                       last_agent_action="reschedule_ask", details_delta=c.delta,
                       details_full=c.details, current_order_id=order_id)

    new_time = slots.extract_time(c.text, expecting_time=True)
    if not new_time or not re.search(r"\d", new_time or ""):
        return _Result(_d("reschedule_ask_time", order_id=order_id),
                       last_agent_action="reschedule_ask", details_delta=c.delta,
                       details_full=c.details, current_order_id=order_id)
    return _Result(
        _d("reschedule_recorded", order_id=order_id, new_time=new_time),
        last_agent_action="reschedule_done", details_delta=c.delta, details_full=c.details,
        current_order_id=order_id, handoff_required=True,
        handoff_reason="Delivery reschedule request",
    )


def _handle_cancellation(c: _TurnCtx) -> _Result:
    return _Result(
        _d("raw", text="I can help with that. Could you share your order reference and the reason for "
           "cancellation? Our team will confirm whether it can still be cancelled — I can't confirm a "
           "cancellation myself."),
        last_agent_action="cancellation", details_delta=c.delta, details_full=c.details,
    )


def _handle_complaint(c: _TurnCtx) -> _Result:
    text_l = c.text.lower()
    order = c.active_order
    order_id = (order["order_id"] if order else None)
    from laundry_class import slots
    order_id = slots.extract_order_id(c.text) or order_id

    reason_default = ho._INTENT_HANDOFF.get(c.intent, ("Complaint", "High"))[0]

    # customer pressing for approval/compensation -> never promise
    if any(k in text_l for k in ("approved", "will you pay", "pay for", "compensate", "get my money")):
        return _Result(_d("handoff_refund_status"), last_agent_action="handoff",
                       details_delta=c.delta, details_full=c.details,
                       handoff_required=True, handoff_reason=reason_default,
                       current_order_id=order_id)

    # Continuation of a complaint we already handed off: acknowledge the new detail
    # and add it to the case rather than repeating the same handoff message.
    if c.laa == "handoff":
        return _Result(
            _d("raw", text="Thank you — I've added those details to the case for the Laundry Class "
               "team. They'll review the order and contact you. A clear photo of the item helps if "
               "you can send one."),
            last_agent_action="handoff", details_delta=c.delta, details_full=c.details,
            handoff_required=True, handoff_reason=reason_default, current_order_id=order_id)

    if c.intent == I.REFUND:
        ask = "Could you tell me what went wrong so I can pass the details to our team?"
        reason = "Refund request"
    elif c.intent == I.DAMAGE:
        ask = "Could you share your order reference, a clear photo of the item, and the delivery date?"
        reason = "Damage complaint"
    else:  # missing item
        ask = "Could you share your order reference and which item is missing?"
        reason = "Missing or lost item"

    ack = "I'm really sorry to hear that."
    return _Result(_d("handoff", ack=ack, ask=ask), last_agent_action="handoff",
                   details_delta=c.delta, details_full=c.details,
                   handoff_required=True, handoff_reason=reason, current_order_id=order_id,
                   customer_name=(order.get("customer_name") if order else c.details.get("customer_name")))


def _handle_payment(c: _TurnCtx) -> _Result:
    decision = ho.decide(I.PAYMENT, c.text)
    if decision.required:  # dispute
        return _Result(
            _d("handoff", ack="I'm sorry about the payment issue.",
               ask="Could you share your order reference and the date of the charge? Please don't "
                   "share your full card number, CVV, PIN, or any OTP — the team never needs those."),
            last_agent_action="handoff", details_delta=c.delta, details_full=c.details,
            handoff_required=True, handoff_reason="Payment dispute",
        )
    return _Result(_d("payment_info"), last_agent_action="payment",
                   details_delta=c.delta, details_full=c.details)


def _handle_special_item(c: _TurnCtx) -> _Result:
    from laundry_class import slots
    extracted = slots.extract_items(c.text)
    if extracted:
        item_label = extracted[0]["item"]
        lookup = extracted[0]["raw"]
    else:
        # a follow-up ("just give me an estimate", "collect it today") — reuse the
        # item we were already discussing so context isn't lost.
        item_label = c.details.get("_pending_item") or c.text.strip()
        lookup = item_label
    entry = kb.find_price(lookup)

    # explicit collection/acceptance request for an unconfirmed special item ->
    # manual review handoff (never confirm collection before inspection).
    if _COLLECT_REQUEST.search(c.text) and (entry is None or entry.inspection_required):
        return _Result(
            _d("handoff", ack="I can't confirm collection for that item yet.",
               ask="Our team needs to inspect it first to confirm whether we can accept it and how "
                   "it should be handled. I've created a review request and they'll get back to you."),
            last_agent_action="handoff", details_delta={}, details_full=c.details,
            handoff_required=True, handoff_reason="Special-care item requires confirmation")
    if entry is None:
        return _Result(_d("price_unknown_item", item=item_label), last_agent_action="special_item",
                       details_delta={"_pending_item": item_label}, details_full=c.details)
    if entry.inspection_required:
        return _Result(_d("price_single", item=entry.item, service=entry.service, price=0,
                          unit=entry.unit, inspection=True),
                       last_agent_action="special_item",
                       details_delta={"_pending_item": entry.item}, details_full=c.details)
    return _Result(_d("price_single", item=entry.item, service=entry.service, price=entry.price_aed,
                      unit=entry.unit), last_agent_action="special_item",
                   details_delta={}, details_full=c.details)


def _handle_human(c: _TurnCtx) -> _Result:
    return _Result(_d("human_ack", ask="Could you share a short description of the issue so I can pass "
                      "it on?"), last_agent_action="human_ack",
                   details_delta=c.delta, details_full=c.details,
                   handoff_required=True, handoff_reason="Customer requested a human agent")


def _handle_unknown(c: _TurnCtx) -> _Result:
    streak = c.fallback_streak + 1
    if streak >= 3:
        return _Result(_d("handoff", ack="Let me get a team member to help.",
                          ask="I've passed your message to the Laundry Class team so a person can assist."),
                       last_agent_action="handoff", details_delta=c.delta, details_full=c.details,
                       handoff_required=True, handoff_reason="Repeated failure to understand the customer",
                       fallback_streak=streak)
    return _Result(_d("clarify"), last_agent_action="clarify",
                   details_delta=c.delta, details_full=c.details, fallback_streak=streak)


# ---------------------------------------------------------------------------
# Handoff notification node
# ---------------------------------------------------------------------------
def handoff_notify(state: ConversationState) -> dict:
    if not state.get("handoff_required") or state.get("handoff_notified"):
        return {}
    phone = state.get("phone_number", "")
    order = kb.find_order_by_phone(phone)
    customer_name = state.get("customer_name") or (order.get("customer_name") if order else None)
    order_id = state.get("current_order_id") or (order.get("order_id") if order else None)
    summary = state.get("conversation_summary") or _summarize(state)
    notification = ho.format_admin_notification(
        priority=_priority_for(state.get("handoff_reason")),
        reason=state.get("handoff_reason") or "Needs review",
        customer_name=customer_name,
        phone=phone,
        order_id=order_id,
        customer_message=_last_human_text(state),
        summary=summary,
    )
    obs.notify_admin(notification)
    return {"handoff_notified": True, "handoff_status": ho.PENDING}


def _priority_for(reason: str | None) -> str:
    if not reason:
        return "Normal"
    high = ("Refund", "Damage", "Missing", "Payment", "Threat", "Hazard", "Angry")
    if any(h.lower() in reason.lower() for h in high):
        return "High"
    return "Medium"


def _summarize(state: ConversationState) -> str:
    turns = [m for m in state.get("messages", []) if isinstance(m, (HumanMessage,))]
    last = turns[-1].content if turns else ""
    return f"Customer (thread {state.get('thread_id')}) needs attention. Latest message: “{last}”."


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
def build_graph(checkpointer):
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(ConversationState)
    g.add_node("agent_turn", agent_turn)
    g.add_node("handoff_notify", handoff_notify)
    g.add_edge(START, "agent_turn")
    g.add_edge("agent_turn", "handoff_notify")
    g.add_edge("handoff_notify", END)
    return g.compile(checkpointer=checkpointer)
