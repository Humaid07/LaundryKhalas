"""Compact, PII-safe classifier input.

This is the ONLY data the classifier ever sees. It deliberately excludes full
phone numbers, full addresses, location coordinates, payment links, facility
margins, full history and unrelated orders (spec: "Send only information
required for classification"). The backend builds it from durable state before
calling the model — the classifier never reads the database itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# how many recent turns we ever include (spec: "last two or three")
MAX_RECENT_CONTEXT = 3
# hard cap on any single text we pass to the model (defensive truncation)
MAX_TEXT_CHARS = 1200


@dataclass
class MessageInput:
    text: str = ""
    message_type: str = "text"          # text | interactive | location | image | audio
    provider_message_id: str | None = None
    has_image: bool = False
    has_audio: bool = False
    has_location: bool = False
    timestamp: str | None = None

    def sanitized_text(self) -> str:
        return (self.text or "")[:MAX_TEXT_CHARS]


@dataclass
class ConversationInput:
    customer_lifecycle: str = "NEW_PROSPECT"     # backend-resolved (LIFECYCLE_STAGES)
    active_order: bool = False
    workflow_state: str | None = None
    selected_service: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    human_takeover: bool = False
    market: str = "UAE"
    currency: str = "AED"
    # true when the assistant's last turn offered a numbered pickup-slot list —
    # lets a bare "2" resolve to PICKUP_SLOT_SELECTION rather than UNKNOWN.
    has_active_slot_options: bool = False
    # true when the assistant's last turn asked a yes/no (e.g. reuse address,
    # confirm order, arrange cash) — lets a bare "yes" be interpreted in context.
    last_assistant_was_question: bool = False


@dataclass
class KnownSignals:
    exact_button_payload: str | None = None
    deterministic_opt_out: bool = False
    deterministic_human_request: bool = False
    # a known, stable interactive selection id (pickup slot / order button etc.)
    known_selection_id: str | None = None


@dataclass
class RecentContextItem:
    role: str    # "assistant" | "user"
    text: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "text": (self.text or "")[:MAX_TEXT_CHARS]}


@dataclass
class ClassifierInput:
    message: MessageInput = field(default_factory=MessageInput)
    conversation: ConversationInput = field(default_factory=ConversationInput)
    recent_context: list[RecentContextItem] = field(default_factory=list)
    known_signals: KnownSignals = field(default_factory=KnownSignals)

    def to_payload(self) -> dict[str, Any]:
        """The compact JSON payload rendered into the classifier user message.
        Byte-identical structure across turns (only values change) so the stable
        prompt prefix stays cacheable."""
        m = self.message
        c = self.conversation
        k = self.known_signals
        return {
            "message": {
                "text": m.sanitized_text(),
                "message_type": m.message_type,
                "provider_message_id": m.provider_message_id,
                "has_image": m.has_image,
                "has_audio": m.has_audio,
                "has_location": m.has_location,
                "timestamp": m.timestamp,
            },
            "conversation": {
                "customer_lifecycle": c.customer_lifecycle,
                "active_order": c.active_order,
                "workflow_state": c.workflow_state,
                "selected_service": c.selected_service,
                "missing_fields": list(c.missing_fields),
                "human_takeover": c.human_takeover,
                "market": c.market,
                "currency": c.currency,
                "has_active_slot_options": c.has_active_slot_options,
                "last_assistant_was_question": c.last_assistant_was_question,
            },
            "recent_context": [i.as_dict() for i in self.recent_context[-MAX_RECENT_CONTEXT:]],
            "known_signals": {
                "exact_button_payload": k.exact_button_payload,
                "deterministic_opt_out": k.deterministic_opt_out,
                "deterministic_human_request": k.deterministic_human_request,
                "known_selection_id": k.known_selection_id,
            },
        }
