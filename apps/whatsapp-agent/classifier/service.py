"""Classifier orchestration — the single entry point the pipeline calls.

``classify_turn`` runs the full flow for one aggregated logical turn:

    deterministic pre-classification  (no LLM if terminal)
      → live Sonnet-5 forced-tool call (production, when live_llm_ready)
      → deterministic rule engine      (offline/tests, or classifier disabled)

Failure/timeout of the live call yields a safe UNKNOWN/FAILED classification
routed to the main agent (spec) — it never raises into the reply path and never
blocks the customer.

The classifier NEVER sends a message, calls a DB tool, calculates a price, or
performs a route. It returns a validated ``Classification``; the router decides.
"""
from __future__ import annotations

import structlog

from classifier import rule_engine
from classifier.context import ClassifierInput
from classifier.deterministic import preclassify
from classifier.prompt import SYSTEM_PROMPT, build_user_payload
from classifier.schema import (
    CLASSIFIER_TOOL_NAME,
    CLASSIFIER_TOOL_SCHEMA,
    Classification,
    ClassifierStatus,
)
from settings import Settings, get_settings

logger = structlog.get_logger(__name__)


async def classify_turn(ci: ClassifierInput, *, settings: Settings | None = None) -> Classification:
    """Classify one aggregated logical customer turn. Never raises."""
    s = settings or get_settings()

    if not s.whatsapp_classifier_enabled:
        c = Classification.unknown(status=ClassifierStatus.FAILED)
        c.reason_codes = ["CLASSIFIER_FAILED"]
        return c

    # 1) deterministic pre-classification — skip the model entirely when terminal
    pre = preclassify(ci)
    if pre.is_terminal and pre.classification is not None:
        return pre.classification

    # 2) live model path (production). Anthropic-only; requires live readiness.
    if s.live_llm_ready and s.ai_provider_effective == "anthropic":
        from llm import service as llm_service

        parsed, result, latency_ms, ok, err = await llm_service.classify_structured(
            SYSTEM_PROMPT,
            build_user_payload(ci),
            tool=CLASSIFIER_TOOL_SCHEMA,
            tool_name=CLASSIFIER_TOOL_NAME,
            max_tokens=s.whatsapp_classifier_max_tokens,
            timeout_seconds=max(0.1, s.whatsapp_classifier_timeout_ms / 1000),
        )
        if ok and parsed is not None and result is not None:
            c = Classification.from_tool_input(
                parsed, model=s.classifier_model_effective, status=ClassifierStatus.OK
            )
            c.latency_ms = latency_ms
            c.tokens_in = result.tokens_in
            c.tokens_out = result.tokens_out
            c.cache_read_tokens = result.cache_read_tokens
            c.cache_write_tokens = result.cache_write_tokens
            c.cost_usd = result.cost_usd
            return _apply_confidence_policy(c, s)
        # live failure/timeout → safe UNKNOWN, main agent still has workflow state
        logger.warning("classifier_live_failed", error=err, latency_ms=round(latency_ms, 1))
        c = Classification.unknown(
            status=ClassifierStatus.FAILED, model=s.classifier_model_effective
        )
        c.latency_ms = latency_ms
        return c

    # 3) offline / classifier-not-live → deterministic rule engine
    c = rule_engine.classify(ci)
    return _apply_confidence_policy(c, s)


def _apply_confidence_policy(c: Classification, s: Settings) -> Classification:
    """Confidence-threshold safety net (spec):

    * >= high  → use as-is (already validated).
    * low..high→ keep the label but flag uncertainty for the main agent.
    * < low    → downgrade to UNKNOWN / NEEDS_CLARIFICATION so a low-confidence
      read never drives a destructive state change.

    Mandatory human-escalation is NEVER downgraded here — safety-sensitive
    complaints bias toward escalation even at lower confidence (the deterministic
    layer + router also enforce this).
    """
    high = s.whatsapp_classifier_high_confidence
    low = s.whatsapp_classifier_low_confidence

    if c.requires_human:
        return c  # never soften a mandatory escalation

    if c.intent_confidence < low and c.primary_intent not in ("UNKNOWN",):
        c.needs_clarification = True
        if not c.clarification_topic:
            c.clarification_topic = "UNKNOWN_INTENT"
        if c.conversation_route not in ("HUMAN_INTERVENTION", "OPERATIONS_EVENT"):
            c.conversation_route = "NEEDS_CLARIFICATION"
        if "LOW_CONFIDENCE" not in c.reason_codes:
            c.reason_codes = [*c.reason_codes, "LOW_CONFIDENCE"][:8]
    elif c.intent_confidence < high:
        # mid-band: main agent proceeds but is told the read is uncertain
        if "LOW_CONFIDENCE" not in c.reason_codes:
            c.reason_codes = [*c.reason_codes, "LOW_CONFIDENCE"][:8]
    return c
