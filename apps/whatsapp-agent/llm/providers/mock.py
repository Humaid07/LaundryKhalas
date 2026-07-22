"""Deterministic, zero-cost provider. Default for local/test mode and the
safe fallback whenever a real provider isn't configured.

Not a real language model - it reads the structured system facts the agent
builds (see agents/whatsapp_agent/agent.py: a "Message intent: ..." line
always first, then - for non-smalltalk intents - a "Booking slots
collected so far" line covering the WHOLE conversation, not just the
latest message) and reacts to them directly, rather than trying to
generate free text. Replies are kept to one short sentence, WhatsApp-style.

This is a rule-based responder, not an NLU model - it will always have an
accuracy ceiling a real LLM doesn't. Enabling LLM_PROVIDER=anthropic (or
openai) with a real API key swaps this out for genuine language
understanding; see settings.py / docs/architecture/standalone-whatsapp-
agent.md.
"""
import re

from llm.providers.base import LLMMessage, LLMProvider, LLMResult
from rules import mock_tags, service_labels, welcome_message

_INTENT_FACT = re.compile(r"Message intent:\s*([a-z_]+)\.")
_SLOTS_FACT = re.compile(
    r"service:\s*([^;]+);\s*area:\s*([^;]+);\s*time:\s*([^;]+); still missing:\s*([^.]+)\."
)
_PRICE_FACT = re.compile(r"Known price for \w+: ([\d.]+ \w+ per \w+ \(minimum [\d.]+ \w+\))\.")
_PRICE_UNAVAILABLE_FACT = re.compile(r"No configured price exists yet for")
# Services priced only after inspection/measurement (bag spa, tailoring,
# carpet/curtain) — defer to the team rather than quoting an exact figure.
_PRICE_MANUAL_FACT = re.compile(r"priced after inspection/measurement")
_ORDER_FLOW_FACT = re.compile(
    r"Order-flow action:\s*(\w+)\. Order ID provided this turn:\s*([^.]+)\."
    r"(?:\s*New pickup time provided this turn:\s*([^.]+)\.)?"
)
_ADD_ITEMS_FACT = re.compile(
    r"Order-flow action: add_items_request\. Items described this turn:\s*([^.]*)\."
)

_NOT_GIVEN = "not given yet"

# All service labels, demo-mode wording and the welcome text are read from
# the rule config (config/laundry_services.json, mock_mode_rules.json,
# whatsapp_agent_rules.json) - not hardcoded here.
_SERVICE_LABELS = service_labels()

WELCOME_TEXT = welcome_message()

_SMALLTALK_REPLIES = {
    "greeting": WELCOME_TEXT,
    "smalltalk_thanks": "You're welcome! Let us know if you need anything else.",
    "smalltalk_farewell": "Thanks for reaching out to LaundryKhalaas — have a great day!",
}

_MOCK_TAGS = mock_tags()
_DEMO_ORDER_TAG = _MOCK_TAGS["order_tag"]
_DEMO_SUPPORT_TAG = _MOCK_TAGS["support_tag"]
_DEMO_BOOKING_ACK = _MOCK_TAGS["booking_ack"]


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult:
        system_text = " ".join(m.content for m in messages if m.role == "system")

        intent_match = _INTENT_FACT.search(system_text)
        intent = intent_match.group(1) if intent_match else None

        if intent in _SMALLTALK_REPLIES or "Reply as: greeting" in system_text:
            reply_key = intent if intent in _SMALLTALK_REPLIES else "greeting"
            return LLMResult(text=_SMALLTALK_REPLIES[reply_key], provider=self.name, model="mock-1")

        if intent == "confirmation_no":
            return LLMResult(
                text="No problem! Let us know if you change your mind or need anything else.",
                provider=self.name,
                model="mock-1",
            )

        if intent == "call_support_request":
            return LLMResult(
                text="Connecting you with our LaundryKhalaas support team. They'll follow up "
                "shortly." + _DEMO_SUPPORT_TAG,
                provider=self.name,
                model="mock-1",
            )

        add_items_match = _ADD_ITEMS_FACT.search(system_text)
        if add_items_match:
            items = add_items_match.group(1).strip()
            if items and items != _NOT_GIVEN:
                text = f"Got it — noted to add: {items}. Our team will confirm this with you." + _DEMO_ORDER_TAG
            else:
                text = "Sure. Please tell me what items you would like to add to your laundry order."
            return LLMResult(text=text, provider=self.name, model="mock-1")

        order_match = _ORDER_FLOW_FACT.search(system_text)
        if order_match:
            action, order_id_raw, new_time_raw = order_match.groups()
            order_id = None if order_id_raw.strip() == _NOT_GIVEN else order_id_raw.strip()
            new_time = None if (new_time_raw or "").strip() in ("", _NOT_GIVEN) else new_time_raw.strip()

            if action == "track_order_request":
                text = (
                    f"Thanks — checking Order {order_id} for you.{_DEMO_ORDER_TAG} Our team "
                    "will confirm the actual status."
                    if order_id
                    else "Sure. Please share your LaundryKhalaas order ID so I can help you "
                    "check the status." + _DEMO_ORDER_TAG
                )
            elif action == "cancel_order_request":
                text = (
                    f"Got it — Order {order_id} noted. Our LaundryKhalaas team will confirm "
                    "whether it can still be cancelled." + _DEMO_ORDER_TAG
                    if order_id
                    else "Sure. Please share your order ID. Our team will confirm whether the "
                    "order can still be cancelled." + _DEMO_ORDER_TAG
                )
            else:  # change_pickup_time_request
                if order_id and new_time:
                    text = (
                        f"Got it — request to move Order {order_id}'s pickup to {new_time} "
                        "noted. Our team will confirm availability." + _DEMO_ORDER_TAG
                    )
                else:
                    text = (
                        "Please share your order ID and the new pickup time you prefer. Our "
                        "team will confirm availability." + _DEMO_ORDER_TAG
                    )
            return LLMResult(text=text, provider=self.name, model="mock-1")

        price_match = _PRICE_FACT.search(system_text)
        if price_match:
            text = f"That's {price_match.group(1)}. Want to book a pickup?"
            return LLMResult(text=text, provider=self.name, model="mock-1")

        if _PRICE_UNAVAILABLE_FACT.search(system_text) or _PRICE_MANUAL_FACT.search(system_text):
            return LLMResult(
                text="Our team will confirm the exact price for that with you shortly.",
                provider=self.name,
                model="mock-1",
            )

        slots_match = _SLOTS_FACT.search(system_text)
        if not slots_match:
            return LLMResult(
                text="Great. Which service do you need today?",
                provider=self.name,
                model="mock-1",
            )

        service_raw, area_raw, time_raw, missing_raw = slots_match.groups()
        service = None if service_raw.strip() == _NOT_GIVEN else service_raw.strip()
        area = None if area_raw.strip() == _NOT_GIVEN else area_raw.strip()
        time_hint = None if time_raw.strip() == _NOT_GIVEN else time_raw.strip()
        missing = [m.strip() for m in missing_raw.split(",")]

        if "none" in missing_raw:
            if intent == "confirmation_yes":
                text = "Perfect! Our team will be in touch shortly to confirm your pickup."
            else:
                service_label = _SERVICE_LABELS.get(service, service or "your service")
                text = f"Got it — {service_label}, {area}, {time_hint}. Our team will confirm the exact pickup window shortly."
            # RULE 4/9 — never imply a real order was created in demo mode.
            if _DEMO_BOOKING_ACK:
                text = f"{text} {_DEMO_BOOKING_ACK}"
            return LLMResult(text=text, provider=self.name, model="mock-1")

        if "service" in missing:
            text = "Great. Which service do you need today?"
        elif "area" in missing:
            text = "Perfect. Please share your pickup area or address."
        elif "time" in missing:
            text = "Great, what day or time works for pickup?"
        else:
            text = "Got it, one more detail needed — could you confirm?"

        return LLMResult(text=text, provider=self.name, model="mock-1", tokens_in=0, tokens_out=0)
