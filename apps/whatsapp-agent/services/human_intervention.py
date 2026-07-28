"""Human-intervention orchestration (abuse/threat → pause AI → one holding note).

This is the glue between the deterministic classifier
(services/abuse_classification) and the persistent takeover state
(db/repositories/human_interventions_repo). The webhook calls
``trigger_from_classification`` on the aggregated turn BEFORE any Anthropic call.

Ordering guarantee (spec): classify → persist intervention + PAUSE (one committed
transaction) → THEN send the single customer holding message. A concurrent later
message therefore sees the paused conversation and is stored, never answered.

Idempotency: at most one active intervention per conversation (DB partial-unique
index). Re-processing the same abusive turn / a duplicate webhook / an Anthropic
retry returns the existing event and does NOT resend the holding message
(gated by customer_notice_sent).
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog

from db.repositories import human_interventions_repo as hi_repo
from services import abuse_classification as ac
from services import sanitize

logger = structlog.get_logger(__name__)

# Approved calm transfer messages (spec). The default is deliberately warm and
# non-judgmental; it never mentions abuse, AI, flags, policy or a specific SLA.
HOLDING_MESSAGE = (
    "I'm sorry this situation has been frustrating. Please hold on while one of our "
    "Operations executives reviews the conversation and gets in touch with you."
)


@dataclass(frozen=True)
class InterventionOutcome:
    triggered: bool
    intervention: dict | None
    created: bool
    should_send_notice: bool
    holding_message: str | None


async def trigger_from_classification(
    conversation_id: str,
    classification: ac.EscalationClassification,
    *,
    flagged_message_id: str | None = None,
    flagged_turn_id: str | None = None,
    combined_text: str | None = None,
) -> InterventionOutcome:
    """If the classification requires human intervention, persist the takeover +
    pause the conversation (idempotently) and decide whether the ONE holding
    message still needs sending. Returns an outcome the caller acts on."""
    reason = ac.intervention_reason(classification)
    if reason is None:
        return InterventionOutcome(False, None, False, False, None)

    logger.info("abuse_classification_completed", conversation=conversation_id,
                category=classification.abuse_category, target=classification.abuse_target,
                threat_severity=classification.threat_severity,
                priority=classification.recommended_priority,
                confidence=classification.confidence, reason_codes=classification.reason_codes)

    preview = _sanitized_preview(combined_text)
    intervention, created = await hi_repo.create_and_pause(
        conversation_id, reason=reason, abuse_category=classification.abuse_category,
        abuse_target=classification.abuse_target, threat_severity=classification.threat_severity,
        internal_priority=classification.recommended_priority,
        confidence=classification.confidence, reason_codes=classification.reason_codes,
        flagged_message_id=flagged_message_id, flagged_turn_id=flagged_turn_id,
        sanitized_preview=preview,
    )

    if created:
        logger.info("human_intervention_created", conversation=conversation_id,
                    intervention=intervention["id"], reason=reason,
                    priority=classification.recommended_priority, turn=flagged_turn_id)
        logger.info("automation_paused", conversation=conversation_id,
                    intervention=intervention["id"])
        logger.info("operations_notification_created", conversation=conversation_id,
                    intervention=intervention["id"], reason=reason,
                    priority=classification.recommended_priority)
        if classification.threat_detected and classification.threat_severity in (
            ac.THREAT_HIGH, ac.THREAT_IMMINENT):
            logger.warning("severe_threat_flagged", conversation=conversation_id,
                           intervention=intervention["id"], severity=classification.threat_severity)
    else:
        logger.info("human_intervention_reused", conversation=conversation_id,
                    intervention=intervention["id"])

    # Send the holding message only once per takeover event (idempotent).
    should_send = False
    if not intervention.get("customer_notice_sent"):
        marked = await hi_repo.mark_notice_sent(intervention["id"])
        if marked is not None:               # we won the race to send it
            should_send = True
            logger.info("human_intervention_notice_sent", conversation=conversation_id,
                        intervention=intervention["id"])
        else:
            logger.info("human_intervention_notice_duplicate_prevented",
                        conversation=conversation_id, intervention=intervention["id"])
    else:
        logger.info("human_intervention_notice_duplicate_prevented",
                    conversation=conversation_id, intervention=intervention["id"])

    return InterventionOutcome(
        triggered=True, intervention=intervention, created=created,
        should_send_notice=should_send,
        holding_message=HOLDING_MESSAGE if should_send else None,
    )


class InterventionError(Exception):
    """Raised for a business-rule violation (already claimed, severe-threat release
    without supervisor, unknown intervention). The API maps these to 4xx."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_SEVERE = (ac.THREAT_HIGH, ac.THREAT_IMMINENT)


async def claim(intervention_id: str, *, agent_id: str, agent_name: str | None) -> dict:
    """Concurrency-safe claim. Raises InterventionError('conflict') if another
    agent already owns it. AI stays paused (claiming never resumes automation)."""
    row = await hi_repo.claim(intervention_id, agent_id=agent_id, agent_name=agent_name)
    if row is None:
        existing = await hi_repo.get(intervention_id)
        if existing is None:
            raise InterventionError("not_found", "Intervention not found.")
        raise InterventionError(
            "conflict",
            f"Already assigned to {existing.get('assigned_agent_name') or 'another agent'}.")
    logger.info("conversation_claimed", conversation=row["conversation_id"],
                intervention=intervention_id, agent=agent_id)
    return row


async def resolve(intervention_id: str, *, agent_id: str, resolution_reason: str | None,
                  close: bool = False) -> dict:
    row = await hi_repo.resolve(intervention_id, agent_id=agent_id,
                                resolution_reason=resolution_reason, close=close)
    if row is None:
        raise InterventionError("not_found", "Intervention not found or already terminal.")
    # Resolving does NOT resume AI (spec) — the conversation stays human-controlled
    # or is closed; only an explicit release-to-AI resumes automation.
    from db.repositories import conversations_repo
    if close:
        await conversations_repo.resolve(row["conversation_id"])
    logger.info("human_intervention_resolved", conversation=row["conversation_id"],
                intervention=intervention_id, agent=agent_id, close=close)
    return row


async def release_to_ai(intervention_id: str, *, agent_id: str, is_supervisor: bool) -> dict:
    """Explicit, authorized return to AI. Severe threats require a supervisor
    (admin) role. Resumes automation and clears the conversation pause."""
    current = await hi_repo.get(intervention_id)
    if current is None:
        raise InterventionError("not_found", "Intervention not found.")
    if current.get("threat_severity") in _SEVERE and not is_supervisor:
        raise InterventionError(
            "forbidden", "Releasing a severe-threat conversation to AI requires a supervisor.")
    row = await hi_repo.release_to_ai(intervention_id)
    if row is None:
        raise InterventionError("not_found", "Intervention not found or already terminal.")
    from db.repositories import conversations_repo
    await conversations_repo.return_to_bot(row["conversation_id"])
    logger.info("conversation_released_to_ai", conversation=row["conversation_id"],
                intervention=intervention_id, agent=agent_id)
    return row


def _sanitized_preview(text: str | None, limit: int = 120) -> str:
    """A masked, length-capped preview for the queue list (no PII, no full graphic
    text). The full message stays behind the authorized conversation view."""
    if not text:
        return ""
    masked = sanitize.sanitize_text(text)
    masked = masked.strip().replace("\n", " ")
    if len(masked) > limit:
        masked = masked[:limit].rstrip() + "…"
    return masked
