"""Provider-neutral data models for the replay harness.

These are plain dataclasses (no DB coupling) so parsing and evaluation can be
unit-tested without a database or LLM. The runner maps them onto the real
agent pipeline; the reports serialize them.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


class Direction(str, enum.Enum):
    """Classification of a single parsed archive message."""

    INBOUND_CUSTOMER = "INBOUND_CUSTOMER"
    OUTBOUND_HISTORICAL_STAFF = "OUTBOUND_HISTORICAL_STAFF"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    MEDIA_MESSAGE = "MEDIA_MESSAGE"
    UNSUPPORTED_MESSAGE = "UNSUPPORTED_MESSAGE"
    EMPTY_MESSAGE = "EMPTY_MESSAGE"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    SYSTEM = "system"
    UNKNOWN = "unknown"


# Media reference where the message points at a binary that is not present in
# the archive (e.g. thumbnails only, or an omitted attachment).
MEDIA_BINARY_UNAVAILABLE = "MEDIA_PRESENT_BINARY_UNAVAILABLE"


@dataclass
class ParsedMessage:
    """One message extracted from an archive conversation export."""

    source_chat_id: str
    source_filename: str
    source_message_id: str
    direction: Direction
    message_type: MessageType
    text: str = ""
    caption: str = ""
    timestamp: Optional[datetime] = None
    sender_label: str = ""
    sender_identifier_hash: str = ""
    media_reference: Optional[str] = None
    media_available: bool = True
    quoted_message_reference: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    location_data: Optional[dict[str, Any]] = None
    contact_data: Optional[dict[str, Any]] = None

    @property
    def is_inbound(self) -> bool:
        return self.direction == Direction.INBOUND_CUSTOMER

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["direction"] = self.direction.value
        d["message_type"] = self.message_type.value
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


@dataclass
class Conversation:
    """A single parsed conversation from the archive."""

    source_archive: str
    source_chat_id: str
    source_filename: str
    customer_identifier_hash: str
    messages: list[ParsedMessage] = field(default_factory=list)
    # Set by the fingerprint/dedup pass.
    fingerprint: str = ""
    excluded_as_duplicate: bool = False
    duplicate_of: str = ""
    exclusion_reason: str = ""
    # Category assigned by the classifier (best-effort, pre-replay).
    category: str = ""

    @property
    def inbound_messages(self) -> list[ParsedMessage]:
        return [m for m in self.messages if m.direction == Direction.INBOUND_CUSTOMER]

    @property
    def outbound_messages(self) -> list[ParsedMessage]:
        return [
            m for m in self.messages
            if m.direction == Direction.OUTBOUND_HISTORICAL_STAFF
        ]

    @property
    def inbound_count(self) -> int:
        return len(self.inbound_messages)

    @property
    def first_inbound_at(self) -> Optional[datetime]:
        for m in self.inbound_messages:
            if m.timestamp:
                return m.timestamp
        return None

    @property
    def last_inbound_at(self) -> Optional[datetime]:
        for m in reversed(self.inbound_messages):
            if m.timestamp:
                return m.timestamp
        return None


@dataclass
class ModelUsage:
    """Anthropic usage for a single model call (or summed over a turn)."""

    model_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    latency_ms: int = 0
    stop_reason: str = ""
    tool_loop_rounds: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, other: "ModelUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        self.cache_creation_input_tokens += other.cache_creation_input_tokens
        self.latency_ms += other.latency_ms
        self.tool_loop_rounds += other.tool_loop_rounds
        self.estimated_cost_usd += other.estimated_cost_usd
        if other.model_id and not self.model_id:
            self.model_id = other.model_id


@dataclass
class ToolCallCapture:
    tool_name: str
    validated_arguments: dict[str, Any] = field(default_factory=dict)
    safe_result_summary: str = ""
    success: bool = True
    failure_type: str = ""
    duration_ms: int = 0
    state_changed: bool = False


@dataclass
class EvalFinding:
    """A single evaluation finding on a turn or conversation."""

    code: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW | INFO
    message: str
    expected: str = ""
    actual: str = ""


@dataclass
class Divergence:
    turn_index: int
    divergence_type: str
    agent_requested_field: str = ""
    historical_customer_message: str = ""


@dataclass
class ReplayTurn:
    """One replayed customer turn and everything captured from the pipeline."""

    source_chat_id: str
    turn_index: int
    # Inbound (exact, preserved) — may be several fragments aggregated into one turn.
    customer_message: str
    customer_fragments: list[str] = field(default_factory=list)
    # Current agent output.
    agent_reply: str = ""
    raw_model_response: str = ""
    # Historical staff reply shown BESIDE (never fed to the agent).
    historical_reply: str = ""
    # Workflow / backend state captured from real tool results & DB.
    detected_intent: str = ""
    resolved_service: str = ""
    resolved_item: str = ""
    service_code: str = ""
    pricing_type: str = ""
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    pre_discount_total: Optional[float] = None
    discount_percentage: Optional[float] = None
    discount_amount: Optional[float] = None
    final_total: Optional[float] = None
    catalogue_version: str = ""
    missing_fields_before: list[str] = field(default_factory=list)
    missing_fields_after: list[str] = field(default_factory=list)
    order_state_before: str = ""
    order_state_after: str = ""
    pickup_slot_options: list[str] = field(default_factory=list)
    selected_pickup_slot: str = ""
    facility_selection_result: str = ""
    human_intervention_status: str = ""
    additional_notes: str = ""
    confirmation_status: str = ""
    # Style normalizations applied by the agent's reply_style layer.
    style_normalizations: list[str] = field(default_factory=list)
    emoji_removed: bool = False
    dash_normalized: bool = False
    exclamation_normalized: bool = False
    response_word_count: int = 0
    response_character_count: int = 0
    # Technical capture.
    tool_calls: list[ToolCallCapture] = field(default_factory=list)
    usage: ModelUsage = field(default_factory=ModelUsage)
    # Evaluation.
    findings: list[EvalFinding] = field(default_factory=list)
    divergence: Optional[Divergence] = None
    # Media context on the originating inbound message, if any.
    media_type: str = ""
    media_available: bool = True
    error: str = ""

    def worst_severity(self) -> str:
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        present = {f.severity for f in self.findings}
        for sev in order:
            if sev in present:
                return sev
        return ""


@dataclass
class ReplayConversationResult:
    """The full replayed conversation: metadata + turns + rollups."""

    replay_run_id: str
    source_archive: str
    source_chat_id: str
    source_filename: str
    synthetic_customer_id: str
    synthetic_conversation_id: str
    category: str = ""
    replay_status: str = "pending"  # pending|running|completed|failed|skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    turns: list[ReplayTurn] = field(default_factory=list)
    historical_outbound_count: int = 0
    final_order_state: str = ""
    order_confirmed: bool = False
    error: str = ""

    # ---- rollups -----------------------------------------------------------
    def _count_sev(self, sev: str) -> int:
        return sum(1 for t in self.turns for f in t.findings if f.severity == sev)

    @property
    def critical_failures(self) -> int:
        return self._count_sev("CRITICAL")

    @property
    def high_failures(self) -> int:
        return self._count_sev("HIGH")

    @property
    def medium_failures(self) -> int:
        return self._count_sev("MEDIUM")

    @property
    def low_failures(self) -> int:
        return self._count_sev("LOW")

    @property
    def divergence_count(self) -> int:
        return sum(1 for t in self.turns if t.divergence is not None)

    @property
    def agent_reply_count(self) -> int:
        return sum(1 for t in self.turns if t.agent_reply)

    @property
    def average_reply_words(self) -> float:
        replies = [t.response_word_count for t in self.turns if t.agent_reply]
        return round(sum(replies) / len(replies), 1) if replies else 0.0

    @property
    def maximum_reply_words(self) -> int:
        replies = [t.response_word_count for t in self.turns if t.agent_reply]
        return max(replies) if replies else 0

    @property
    def usage_total(self) -> ModelUsage:
        total = ModelUsage()
        for t in self.turns:
            total.add(t.usage)
        return total

    @property
    def overall_result(self) -> str:
        if self.replay_status == "failed":
            return "ERROR"
        if self.critical_failures:
            return "CRITICAL"
        if self.high_failures:
            return "FAIL"
        if self.medium_failures:
            return "WARN"
        return "PASS"

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds(), 1)
        return 0.0
