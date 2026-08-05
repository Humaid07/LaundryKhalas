"""Classifier-aware router — RECOMMEND ONLY.

The classifier recommends a route; the backend router validates it against the
deterministic signals and current state before anything acts on it. In Stage 1
(shadow mode) the router's decision is RECORDED and COMPARED against the existing
production routing, but production routing stays authoritative — nothing here
sends a message or mutates state.

``select_route`` returns a ``RouteDecision`` describing what WOULD happen. The
webhook hook logs it; wiring it to actually control routing is Stage 2+, gated by
WHATSAPP_CLASSIFIER_ALLOW_ROUTING / _ALLOW_HUMAN_ESCALATION.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from classifier.context import ClassifierInput
from classifier.schema import Classification
from classifier import taxonomy as tax


# Stage 2 low-risk categories — the ONLY intents whose classifier route may take
# over from the main agent when routing is enabled. Deliberately excludes
# pricing, repairs, complaints, refunds, B2B and anything human-facing/ambiguous.
LOW_RISK_INTENTS: frozenset[str] = frozenset({
    "GREETING",
    "SERVICE_ENQUIRY",
    "SERVICE_SELECTION",
    "PROCESS_ENQUIRY",
    "ADDRESS_PROVIDED",
    "PICKUP_SLOT_ENQUIRY",
    "PAYMENT_METHOD_ENQUIRY",
})


def should_route_via_classifier(c: Classification, decision: "RouteDecision", settings) -> bool:
    """Stage 2 gate: may the validated classification actually control routing?

    Returns False in shadow mode, when routing is disabled, for any non-low-risk
    intent, below the high-confidence threshold, or whenever human intervention /
    clarification is involved. Deterministic escalation and the main agent remain
    the safe default whenever this returns False. This function CHANGES nothing on
    its own — the caller decides what to do with a True.
    """
    if settings.whatsapp_classifier_shadow_mode:
        return False
    if not settings.whatsapp_classifier_allow_routing:
        return False
    if c.requires_human or c.needs_clarification:
        return False
    if c.primary_intent not in LOW_RISK_INTENTS:
        return False
    if c.intent_confidence < settings.whatsapp_classifier_high_confidence:
        return False
    # only routes the classifier itself considers safe to short-circuit
    return decision.route in ("DETERMINISTIC_HANDLER", "MAIN_AGENT")


@dataclass
class RouteDecision:
    route: str                      # one of taxonomy.CONVERSATION_ROUTES
    requires_human: bool = False
    human_reason: str | None = None
    fixed_template_id: str | None = None
    needs_clarification: bool = False
    should_cancel_followups: bool = True
    # true when the decision was overridden by a deterministic safety rule rather
    # than taken from the classifier's recommendation (audited in shadow logs).
    validated_override: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "route": self.route,
            "requires_human": self.requires_human,
            "human_reason": self.human_reason,
            "fixed_template_id": self.fixed_template_id,
            "needs_clarification": self.needs_clarification,
            "should_cancel_followups": self.should_cancel_followups,
            "validated_override": self.validated_override,
            "notes": list(self.notes),
        }


def select_route(c: Classification, ci: ClassifierInput) -> RouteDecision:
    """Validate the classifier's recommendation into a concrete route decision.

    Safety precedence (independent of the model's own route field):
      1. mandatory human reason        → HUMAN_INTERVENTION
      2. explicit clarification signal → NEEDS_CLARIFICATION
      3. deterministic template ready  → DETERMINISTIC_HANDLER
      4. otherwise                     → the classifier's recommended route,
         defaulting to MAIN_AGENT.
    """
    notes: list[str] = []

    # 1) Mandatory human escalation wins over any softer recommended route.
    if c.requires_human and c.human_reason in tax.MANDATORY_HUMAN_REASONS:
        override = c.conversation_route != "HUMAN_INTERVENTION"
        if override:
            notes.append("forced_human_intervention")
        return RouteDecision(
            route="HUMAN_INTERVENTION",
            requires_human=True,
            human_reason=c.human_reason,
            fixed_template_id=c.fixed_template_id,
            should_cancel_followups=c.should_cancel_followups,
            validated_override=override,
            notes=notes,
        )

    # 2) Explicit clarification need.
    if c.needs_clarification and not c.requires_human:
        return RouteDecision(
            route="NEEDS_CLARIFICATION",
            needs_clarification=True,
            should_cancel_followups=c.should_cancel_followups,
            validated_override=c.conversation_route != "NEEDS_CLARIFICATION",
            notes=["clarification_required"],
        )

    # 3) Deterministic template: only when the classifier both recommended it AND
    #    named a known template id. The backend still checks required data exists
    #    before actually rendering it (that check is Stage 2 in the real handler).
    if c.conversation_route == "DETERMINISTIC_HANDLER" and c.fixed_template_id in tax.FIXED_TEMPLATE_IDS:
        return RouteDecision(
            route="DETERMINISTIC_HANDLER",
            fixed_template_id=c.fixed_template_id,
            should_cancel_followups=c.should_cancel_followups,
            notes=["template_candidate"],
        )

    # 4) Fall back to the classifier's recommendation (validated to the vocab),
    #    defaulting to the main agent.
    route = c.conversation_route if c.conversation_route in tax.CONVERSATION_ROUTES else "MAIN_AGENT"
    if route in ("HUMAN_INTERVENTION",):  # requires_human wasn't mandatory → don't escalate on model's say-so alone
        route = "MAIN_AGENT"
        notes.append("downgraded_unvalidated_human")
    return RouteDecision(
        route=route,
        fixed_template_id=None,
        should_cancel_followups=c.should_cancel_followups,
        notes=notes,
    )
