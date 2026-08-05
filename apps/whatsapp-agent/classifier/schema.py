"""Strict classifier output contract.

Two representations:

  * ``Classification`` — the validated in-process dataclass the router, the
    persistence repo and the main-agent hint all consume.
  * ``CLASSIFIER_TOOL_SCHEMA`` — the JSON Schema handed to Anthropic as a single
    FORCED tool (tool_choice), so the model must return a structured object and
    we never regex a JSON blob out of prose (spec: "Do not parse intent from
    free-form prose").

``Classification.from_tool_input`` validates every field against the closed
taxonomy and coerces/repairs out-of-range values to safe defaults rather than
raising — a live model very occasionally emits an unknown enum, and one bad
label must never break the customer's turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from classifier import taxonomy as tax


class ClassifierStatus:
    """Lifecycle of a classification attempt (persisted as classifier_status)."""

    OK = "OK"                 # live model returned a validated result
    DETERMINISTIC = "DETERMINISTIC"   # resolved pre-LLM, no model call
    FALLBACK = "FALLBACK"     # deterministic rule-engine result (no live model)
    FAILED = "FAILED"         # model timed out / errored → UNKNOWN, main agent
    SHADOW = "SHADOW"         # ran in shadow mode (recorded, not routed)


@dataclass
class DetectedEntities:
    mentioned_services: list[str] = field(default_factory=list)
    mentioned_items: list[str] = field(default_factory=list)
    mentioned_quantity: int | None = None
    mentioned_weight_kg: float | None = None
    mentioned_date_text: str | None = None
    mentioned_time_text: str | None = None
    mentioned_order_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_raw(cls, raw: Any) -> "DetectedEntities":
        if not isinstance(raw, dict):
            return cls()
        def _str_list(v: Any) -> list[str]:
            if isinstance(v, list):
                return [str(x) for x in v if isinstance(x, (str, int, float))][:20]
            return []
        def _int(v: Any) -> int | None:
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        def _float(v: Any) -> float | None:
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        def _str(v: Any) -> str | None:
            return str(v)[:200] if isinstance(v, (str, int, float)) else None
        return cls(
            mentioned_services=[s for s in _str_list(raw.get("mentioned_services"))
                                if s in tax.SERVICE_DOMAINS],
            mentioned_items=_str_list(raw.get("mentioned_items")),
            mentioned_quantity=_int(raw.get("mentioned_quantity")),
            mentioned_weight_kg=_float(raw.get("mentioned_weight_kg")),
            mentioned_date_text=_str(raw.get("mentioned_date_text")),
            mentioned_time_text=_str(raw.get("mentioned_time_text")),
            mentioned_order_id=_str(raw.get("mentioned_order_id")),
        )


@dataclass
class Classification:
    """One validated classification of one logical customer turn."""

    classification_version: str = tax.CLASSIFICATION_VERSION
    primary_intent: str = "UNKNOWN"
    secondary_intents: list[str] = field(default_factory=list)
    intent_confidence: float = 0.0
    service_domain: str = "UNKNOWN"
    service_subtype: str | None = None
    service_confidence: float = 0.0
    customer_goal: str = "UNKNOWN"
    conversation_route: str = "MAIN_AGENT"
    fixed_template_id: str | None = None
    pricing_intent: str = "NONE"
    payment_intent: str = "NONE"
    repair_intent: str = "NONE"
    complaint_type: str = "NONE"
    sentiment: str = "NEUTRAL"
    frustration_level: int = 0
    urgency: str = "NORMAL"
    requires_human: bool = False
    human_reason: str | None = None
    needs_clarification: bool = False
    clarification_topic: str | None = None
    should_cancel_followups: bool = True
    detected_entities: DetectedEntities = field(default_factory=DetectedEntities)
    reason_codes: list[str] = field(default_factory=list)

    # --- runtime metadata (not part of the model's output) -------------------
    status: str = ClassifierStatus.OK
    classifier_model: str | None = None
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    # ------------------------------------------------------------------ helpers
    @property
    def is_multi_intent(self) -> bool:
        return len(self.secondary_intents) > 0

    def as_output_dict(self) -> dict[str, Any]:
        """The model-facing / persisted classification object (no runtime meta)."""
        return {
            "classification_version": self.classification_version,
            "primary_intent": self.primary_intent,
            "secondary_intents": list(self.secondary_intents),
            "intent_confidence": self.intent_confidence,
            "service_domain": self.service_domain,
            "service_subtype": self.service_subtype,
            "service_confidence": self.service_confidence,
            "customer_goal": self.customer_goal,
            "conversation_route": self.conversation_route,
            "fixed_template_id": self.fixed_template_id,
            "pricing_intent": self.pricing_intent,
            "payment_intent": self.payment_intent,
            "repair_intent": self.repair_intent,
            "complaint_type": self.complaint_type,
            "sentiment": self.sentiment,
            "frustration_level": self.frustration_level,
            "urgency": self.urgency,
            "requires_human": self.requires_human,
            "human_reason": self.human_reason,
            "needs_clarification": self.needs_clarification,
            "clarification_topic": self.clarification_topic,
            "should_cancel_followups": self.should_cancel_followups,
            "detected_entities": self.detected_entities.as_dict(),
            "reason_codes": list(self.reason_codes),
        }

    def main_agent_hint(self) -> dict[str, Any]:
        """Compact projection passed to the main Sonnet agent (spec)."""
        return {
            "primary": self.primary_intent,
            "secondary": list(self.secondary_intents),
            "service_domain": self.service_domain,
            "pricing_intent": self.pricing_intent,
            "payment_intent": self.payment_intent,
            "repair_intent": self.repair_intent,
            "sentiment": self.sentiment,
            "frustration_level": self.frustration_level,
            "needs_clarification": self.needs_clarification,
            "confidence": self.intent_confidence,
        }

    # ------------------------------------------------------------ construction
    @classmethod
    def from_tool_input(
        cls, raw: Any, *, model: str | None = None, status: str = ClassifierStatus.OK
    ) -> "Classification":
        """Validate a model tool-input dict into a Classification, repairing any
        out-of-taxonomy value to a safe default (never raises on bad enums)."""
        raw = raw if isinstance(raw, dict) else {}

        def pick(key: str, vocab: tuple, default: str) -> str:
            v = raw.get(key)
            return v if isinstance(v, str) and v in vocab else default

        def pick_opt(key: str, vocab: tuple) -> str | None:
            v = raw.get(key)
            return v if isinstance(v, str) and v in vocab else None

        def conf(key: str) -> float:
            try:
                f = float(raw.get(key, 0.0))
            except (TypeError, ValueError):
                return 0.0
            return max(0.0, min(1.0, f))

        def flag(key: str, default: bool = False) -> bool:
            v = raw.get(key, default)
            return bool(v) if isinstance(v, bool) else default

        secondary = raw.get("secondary_intents")
        secondary = [s for s in secondary if s in tax.PRIMARY_INTENTS] if isinstance(secondary, list) else []
        # de-dup, drop the primary if it leaked into the secondary list
        primary = pick("primary_intent", tax.PRIMARY_INTENTS, "UNKNOWN")
        secondary = [s for i, s in enumerate(secondary) if s != primary and s not in secondary[:i]][:6]

        reason_codes = raw.get("reason_codes")
        reason_codes = [r for r in reason_codes if r in tax.REASON_CODES][:8] if isinstance(reason_codes, list) else []

        frustration = raw.get("frustration_level", 0)
        try:
            frustration = int(frustration)
        except (TypeError, ValueError):
            frustration = 0
        frustration = frustration if frustration in tax.FRUSTRATION_LEVELS else 0

        human_reason = pick_opt("human_reason", tax.HUMAN_REASONS)
        requires_human = flag("requires_human")
        # keep the two consistent: a mandatory reason implies human required
        if human_reason in tax.MANDATORY_HUMAN_REASONS:
            requires_human = True

        return cls(
            classification_version=str(raw.get("classification_version") or tax.CLASSIFICATION_VERSION),
            primary_intent=primary,
            secondary_intents=secondary,
            intent_confidence=conf("intent_confidence"),
            service_domain=pick("service_domain", tax.SERVICE_DOMAINS, "UNKNOWN"),
            service_subtype=(str(raw["service_subtype"])[:80]
                             if isinstance(raw.get("service_subtype"), str) else None),
            service_confidence=conf("service_confidence"),
            customer_goal=pick("customer_goal", tax.CUSTOMER_GOALS, "UNKNOWN"),
            conversation_route=pick("conversation_route", tax.CONVERSATION_ROUTES, "MAIN_AGENT"),
            fixed_template_id=pick_opt("fixed_template_id", tax.FIXED_TEMPLATE_IDS),
            pricing_intent=pick("pricing_intent", tax.PRICING_INTENTS, "NONE"),
            payment_intent=pick("payment_intent", tax.PAYMENT_INTENTS, "NONE"),
            repair_intent=pick("repair_intent", tax.REPAIR_INTENTS, "NONE"),
            complaint_type=pick("complaint_type", tax.COMPLAINT_TYPES, "NONE"),
            sentiment=pick("sentiment", tax.SENTIMENTS, "NEUTRAL"),
            frustration_level=frustration,
            urgency=pick("urgency", tax.URGENCIES, "NORMAL"),
            requires_human=requires_human,
            human_reason=human_reason,
            needs_clarification=flag("needs_clarification"),
            clarification_topic=pick_opt("clarification_topic", tax.CLARIFICATION_TOPICS),
            should_cancel_followups=flag("should_cancel_followups", True),
            detected_entities=DetectedEntities.from_raw(raw.get("detected_entities")),
            reason_codes=reason_codes,
            status=status,
            classifier_model=model,
        )

    @classmethod
    def unknown(cls, *, status: str = ClassifierStatus.FAILED, model: str | None = None) -> "Classification":
        """The safe fallback classification: route to the main agent, change
        nothing destructive, cancel stale follow-ups on a genuine reply."""
        return cls(
            primary_intent="UNKNOWN",
            intent_confidence=0.0,
            service_domain="UNKNOWN",
            customer_goal="UNKNOWN",
            conversation_route="MAIN_AGENT",
            reason_codes=["CLASSIFIER_FAILED"] if status == ClassifierStatus.FAILED else ["LOW_CONFIDENCE"],
            status=status,
            classifier_model=model,
        )


# --- forced-tool JSON schema -------------------------------------------------
# Handed to Anthropic as the ONLY tool with tool_choice={"type":"tool"}. Enums
# are the taxonomy tuples so the model is constrained to valid values.
def _enum(vocab: tuple) -> list:
    return list(vocab)


CLASSIFIER_TOOL_NAME = "emit_classification"

CLASSIFIER_TOOL_SCHEMA: dict[str, Any] = {
    "name": CLASSIFIER_TOOL_NAME,
    "description": (
        "Return exactly one structured classification of the customer's latest "
        "logical turn. Emit ONLY fields defined here, using ONLY the allowed enum "
        "values. Do not include any explanation, chain-of-thought, or free text."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "classification_version": {"type": "string"},
            "primary_intent": {"type": "string", "enum": _enum(tax.PRIMARY_INTENTS)},
            "secondary_intents": {
                "type": "array",
                "items": {"type": "string", "enum": _enum(tax.PRIMARY_INTENTS)},
            },
            "intent_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "service_domain": {"type": "string", "enum": _enum(tax.SERVICE_DOMAINS)},
            "service_subtype": {"type": ["string", "null"]},
            "service_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "customer_goal": {"type": "string", "enum": _enum(tax.CUSTOMER_GOALS)},
            "conversation_route": {"type": "string", "enum": _enum(tax.CONVERSATION_ROUTES)},
            "fixed_template_id": {"type": ["string", "null"], "enum": _enum(tax.FIXED_TEMPLATE_IDS) + [None]},
            "pricing_intent": {"type": "string", "enum": _enum(tax.PRICING_INTENTS)},
            "payment_intent": {"type": "string", "enum": _enum(tax.PAYMENT_INTENTS)},
            "repair_intent": {"type": "string", "enum": _enum(tax.REPAIR_INTENTS)},
            "complaint_type": {"type": "string", "enum": _enum(tax.COMPLAINT_TYPES)},
            "sentiment": {"type": "string", "enum": _enum(tax.SENTIMENTS)},
            "frustration_level": {"type": "integer", "enum": list(tax.FRUSTRATION_LEVELS)},
            "urgency": {"type": "string", "enum": _enum(tax.URGENCIES)},
            "requires_human": {"type": "boolean"},
            "human_reason": {"type": ["string", "null"], "enum": _enum(tax.HUMAN_REASONS) + [None]},
            "needs_clarification": {"type": "boolean"},
            "clarification_topic": {"type": ["string", "null"], "enum": _enum(tax.CLARIFICATION_TOPICS) + [None]},
            "should_cancel_followups": {"type": "boolean"},
            "detected_entities": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "mentioned_services": {"type": "array", "items": {"type": "string"}},
                    "mentioned_items": {"type": "array", "items": {"type": "string"}},
                    "mentioned_quantity": {"type": ["integer", "null"]},
                    "mentioned_weight_kg": {"type": ["number", "null"]},
                    "mentioned_date_text": {"type": ["string", "null"]},
                    "mentioned_time_text": {"type": ["string", "null"]},
                    "mentioned_order_id": {"type": ["string", "null"]},
                },
            },
            "reason_codes": {
                "type": "array",
                "items": {"type": "string", "enum": _enum(tax.REASON_CODES)},
            },
        },
        "required": [
            "primary_intent",
            "intent_confidence",
            "service_domain",
            "customer_goal",
            "conversation_route",
            "sentiment",
            "urgency",
            "requires_human",
            "needs_clarification",
            "should_cancel_followups",
        ],
    },
}
