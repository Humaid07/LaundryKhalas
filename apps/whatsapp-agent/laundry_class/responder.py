"""The reply-composition layer, exposed as a LangChain chat model.

`LaundryClassChatModel` is a real `langchain_core` `BaseChatModel`: the graph
invokes it with the conversation messages plus a directive (a compact JSON control
block the graph computes from intent + slots + KB + handoff state). By default it is
deterministic and mock — no network, no cost, no invented facts. A live provider
(Anthropic) is swappable via `build_chat_model()` but stays off unless explicitly
enabled, honouring the mock-first rule.

Keeping composition behind a BaseChatModel means the same graph edge works whether the
node is backed by the deterministic composer or a real LLM.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_DIRECTIVE_PREFIX = "LC_DIRECTIVE:"
_CURRENCY = "AED"

WELCOME = (
    "Hi! Welcome to Laundry Class 👋 I can help with prices, pickups, "
    "order status, and delivery. How can I help you today?"
)


# ---------------------------------------------------------------------------
# Directive helpers (graph side)
# ---------------------------------------------------------------------------
def directive_message(kind: str, **payload) -> SystemMessage:
    """Build the control SystemMessage the graph passes to the model."""
    return SystemMessage(content=_DIRECTIVE_PREFIX + json.dumps({"kind": kind, "payload": payload}))


def _extract_directive(messages: list[BaseMessage]) -> dict:
    for msg in reversed(messages):
        if isinstance(msg, SystemMessage) and isinstance(msg.content, str) \
                and msg.content.startswith(_DIRECTIVE_PREFIX):
            return json.loads(msg.content[len(_DIRECTIVE_PREFIX):])
    return {"kind": "unknown", "payload": {}}


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------
def _money(value: float) -> str:
    return f"{_CURRENCY} {int(value) if float(value).is_integer() else round(value, 2)}"


def _name_prefix(name: str | None) -> str:
    return f"{name}, " if name else ""


def compose(directive: dict) -> str:
    kind = directive.get("kind", "unknown")
    p = directive.get("payload", {})
    handler = _HANDLERS.get(kind, _unknown)
    return handler(p)


def _raw(p): return p.get("text", "")


def _greeting(p):
    if p.get("returning") and p.get("name"):
        return f"Welcome back, {p['name']}! How can I help you today?"
    return WELCOME


def _smalltalk_thanks(p):
    return "You're welcome! Let me know if there's anything else I can help with."


def _smalltalk_farewell(p):
    return "Thanks for chatting with Laundry Class — have a great day!"


def _price_single(p):
    item = p["item"]
    service = p.get("service", "")
    if p.get("inspection"):
        return (
            f"For {item.lower()}, the price depends on the fabric and condition, so our team "
            "needs to inspect it before confirming. Prices are in AED."
        )
    price = _money(p["price"])
    unit = p.get("unit", "per piece")
    lead = f"{service} for a {item.lower()}" if service else item
    tail = "" if unit == "per piece" else f" ({unit})"
    followup = " Would you like to arrange a pickup?" if p.get("offer_pickup", True) else ""
    return f"{lead} is {price}{tail}.{followup}"


def _price_multi(p):
    lines = p["lines"]
    body = "\n".join(f"• {ln['label']} — {_money(ln['line_total'])}" for ln in lines)
    subtotal = _money(p["subtotal"])
    out = [f"Here's an estimate (all prices in {_CURRENCY}):", body,
           f"Estimated subtotal: {subtotal} (estimate)."]
    if p.get("free_delivery", True):
        out.append("Pickup and delivery are free and included.")
    if p.get("area_prompt"):
        out.append("Which area should we collect from, so I can confirm the delivery window?")
    if p.get("inspection_note"):
        out.append(p["inspection_note"])
    return "\n".join(out)


def _price_unknown_item(p):
    item = p["item"]
    return (
        f"I don't have an approved price for {item.lower()} in our list. Our team would need to "
        "inspect the item and its material before confirming whether we can accept it and what "
        "it would cost. I can't quote a price I'm not sure of."
    )


def _service_info(p):
    return (
        "We offer Wash & Fold, Wash & Iron, Ironing Only, and Dry Cleaning, plus special-care "
        "items on inspection. Pickup and delivery are free. What would you like — a price or a pickup?"
    )


def _pickup_delivery_info(p):
    return (
        "Pickup and delivery are free and included in our supported Dubai areas, usually within a "
        "2–3 hour window. Which area are you in, so I can confirm availability?"
    )


def _order_ask(p):
    known = p.get("known", {})
    field = p["missing_field"]
    name = known.get("customer_name")
    prompts = {
        "customer_name_area": "Of course! May I have your name and pickup area?",
        "service": f"{_name_prefix(name)}which service do you need — Wash & Fold, Wash & Iron, "
                   "Ironing, or Dry Cleaning?",
        "items": "Great. What items should we clean (for example: 5 shirts, 2 trousers)?",
        "area": "Thanks. Which area should we collect from?",
        "pickup_time": "What day and time would suit you for pickup?",
        "pickup_time_narrow": "What time works for you? You can pick any time between "
                              "9:00 AM and 9:00 PM.",
        "payment_method": "How would you like to pay — cash on delivery, card on delivery, "
                          "or an online payment link?",
    }
    question = prompts.get(field, "Could you share a few more details so I can set up the pickup?")
    estimate_line = p.get("estimate_line")
    return f"{estimate_line}\n\n{question}" if estimate_line else question


def _order_summary(p):
    d = p["details"]
    lines = [
        "Here's your order so far — please review and confirm:",
        f"• Name: {d.get('customer_name', '—')}",
        f"• Service: {d.get('service', '—')}",
        f"• Items: {p.get('items_text', '—')}",
        f"• Area: {d.get('area', '—')}",
        f"• Pickup: {d.get('pickup_time', '—')}",
    ]
    if p.get("subtotal") is not None:
        lines.append(f"• Estimated subtotal: {_money(p['subtotal'])} (estimate)")
    lines.append("• Pickup & delivery: Free")
    lines.append(f"• Payment: {d.get('payment_method', '—')}")
    lines.append("\nShall I record this order? (yes to confirm)")
    return "\n".join(lines)


def _order_confirmed(p):
    d = p["details"]
    ref = p["order_ref"]
    lines = [
        f"Done{(' ' + d['customer_name']) if d.get('customer_name') else ''}! "
        "Your order request has been recorded for testing.",
        f"Reference: {ref}",
        f"Service: {d.get('service', '—')} · Items: {p.get('items_text', '—')}",
        f"Pickup: {d.get('pickup_time', '—')} in {d.get('area', '—')} · "
        f"Payment: {d.get('payment_method', '—')}",
    ]
    if p.get("subtotal") is not None:
        lines.append(f"Estimated subtotal: {_money(p['subtotal'])} (estimate). Pickup & delivery free.")
    lines.append(
        "A team member would normally confirm the pickup details before the order becomes active."
    )
    return "\n".join(lines)


def _order_status(p):
    o = p["order"]
    lines = [
        f"Your order {o['order_id']} is currently: {o['status']}.",
    ]
    if o.get("estimated_delivery_time"):
        lines.append(
            f"Estimated delivery: {o['estimated_delivery_time']}"
            + (f" (window {o['delivery_window']})" if o.get("delivery_window") else "")
            + " — this is an estimate unless confirmed by our team."
        )
    if o.get("actual_delivery_time"):
        lines.append(f"It was delivered on {o['actual_delivery_time']}.")
    return "\n".join(lines)


def _order_recall(p):
    return p["text"]


def _reschedule_ask_time(p):
    return (
        f"I can note a new delivery time for order {p['order_id']}. What time would you prefer?"
    )


def _reschedule_recorded(p):
    return (
        f"I've recorded your request for delivery at {p['new_time']} for order {p['order_id']}. "
        "The timing needs to be confirmed based on the driver's route, so I've passed the request "
        "to the team. I can't confirm the new time yet."
    )


def _handoff(p):
    ack = p.get("ack", "I'm sorry about this.")
    body = (
        " I've recorded the details and passed the case to the Laundry Class team for review. "
        "A team member will follow up with you."
    )
    ask = f" {p['ask']}" if p.get("ask") else ""
    return f"{ack}{body}{ask}"


def _handoff_refund_status(p):
    return (
        "Your request has been submitted for review, but it hasn't been approved yet. "
        "A Laundry Class team member will review the order and contact you. I'm not able to "
        "approve a refund myself."
    )


def _human_ack(p):
    ask = p.get("ask", "Could you share a short description of the issue?")
    return f"Of course — I'm connecting you with the Laundry Class team. {ask}"


def _payment_info(p):
    return (
        "You can pay by cash on delivery, card on delivery, or an online payment link — whichever "
        "is easiest. For your security, never share your full card number, CVV, PIN, or any OTP."
    )


def _clarify(p):
    return p.get(
        "question",
        "Just to make sure I help correctly — are you asking about a price, or would you like to "
        "arrange a pickup?",
    )


def _refuse(p):
    return (
        "I can only help with Laundry Class laundry and cleaning services — prices, pickups, "
        "orders, and delivery. Is there something along those lines I can help with?"
    )


def _unknown(p):
    return _clarify(p)


_HANDLERS = {
    "raw": _raw,
    "greeting": _greeting,
    "smalltalk_thanks": _smalltalk_thanks,
    "smalltalk_farewell": _smalltalk_farewell,
    "price_single": _price_single,
    "price_multi": _price_multi,
    "price_unknown_item": _price_unknown_item,
    "service_info": _service_info,
    "pickup_delivery_info": _pickup_delivery_info,
    "order_ask": _order_ask,
    "order_summary": _order_summary,
    "order_confirmed": _order_confirmed,
    "order_status": _order_status,
    "order_recall": _order_recall,
    "reschedule_ask_time": _reschedule_ask_time,
    "reschedule_recorded": _reschedule_recorded,
    "handoff": _handoff,
    "handoff_refund_status": _handoff_refund_status,
    "human_ack": _human_ack,
    "payment_info": _payment_info,
    "clarify": _clarify,
    "refuse": _refuse,
    "unknown": _unknown,
}


# ---------------------------------------------------------------------------
# LangChain chat model
# ---------------------------------------------------------------------------
class LaundryClassChatModel(BaseChatModel):
    """Deterministic, mock-first chat model. Reads the directive the graph attaches
    and returns the composed WhatsApp reply as an AIMessage."""

    @property
    def _llm_type(self) -> str:
        return "laundry-class-deterministic"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        directive = _extract_directive(messages)
        text = compose(directive)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def build_chat_model():
    """Factory: deterministic model by default; a live provider only if explicitly
    enabled via env (LC_LLM_PROVIDER=anthropic + key). Off by default = mock-first."""
    from laundry_class.config import get_config

    cfg = get_config()
    if cfg.llm_provider == "anthropic" and cfg.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=cfg.llm_model or "claude-opus-4-8",
                                 api_key=cfg.anthropic_api_key, max_tokens=400)
        except Exception:
            pass  # fall back to deterministic model if the live provider isn't available
    return LaundryClassChatModel()
