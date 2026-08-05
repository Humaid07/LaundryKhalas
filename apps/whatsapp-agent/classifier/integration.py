"""Pipeline integration for the classifier (Stage 1: shadow).

One self-contained, never-raising entry point — ``run_shadow_classification`` —
that the webhook calls AFTER aggregation + state-load and BEFORE the main agent.
It builds the compact PII-safe payload, runs the classifier, validates a route,
persists the result (idempotent, Supabase-only), and emits a structlog event +
usage metrics. In shadow mode it does NOT change routing — the caller ignores the
return value and continues to the main agent exactly as before.

Everything here is best-effort and wrapped so a classifier problem can never
break the customer's turn (CLAUDE.md: the reply path must never crash).
"""
from __future__ import annotations

import structlog

from classifier.context import (
    ClassifierInput,
    ConversationInput,
    KnownSignals,
    MessageInput,
    RecentContextItem,
)
from classifier.lifecycle import LifecycleFacts, resolve_lifecycle
from classifier.router import select_route
from classifier.schema import Classification
from settings import get_settings

logger = structlog.get_logger(__name__)


async def _gather_recent_context(conversation_id: str, exclude: set[str]) -> list[RecentContextItem]:
    """Last few turns (role-mapped), excluding this turn's own fragments. Best
    effort — returns [] on any error."""
    try:
        from db.repositories import messages_repo

        rows = await messages_repo.list_messages(conversation_id)
    except Exception:  # noqa: BLE001
        return []
    items: list[RecentContextItem] = []
    for m in rows[-8:]:
        st = m.get("sender_type")
        txt = m.get("message_text")
        if st not in ("customer", "agent") or not txt or txt in exclude:
            continue
        items.append(RecentContextItem(role="user" if st == "customer" else "assistant", text=txt))
    return items[-3:]


async def _lifecycle_facts(convo: dict, customer: dict, active_draft: dict | None,
                           verified_name: str | None, recent: list[RecentContextItem]) -> LifecycleFacts:
    """Backend-resolved lifecycle facts. ``verified_name`` (a previously confirmed
    customer name) is a reliable proxy for 'has a completed order'. Never raises."""
    has_active = bool(active_draft)
    try:
        from db.repositories import orders_repo

        if not has_active:
            open_order = await orders_repo.get_open_for_conversation(convo["id"])
            has_active = bool(open_order)
    except Exception:  # noqa: BLE001
        pass
    seg = (customer or {}).get("segment") or (customer or {}).get("crm_segment") or ""
    return LifecycleFacts(
        has_completed_order=bool(verified_name),
        has_active_order=has_active,
        has_prior_conversation=len(recent) > 0,
        is_b2b_confirmed=str(seg).lower() in ("b2b", "b2b_lead", "commercial"),
    )


def _selected_service(active_draft: dict | None) -> str | None:
    if not active_draft:
        return None
    return (active_draft.get("service_category_name")
            or active_draft.get("service_code")
            or active_draft.get("service_category_code"))


async def run_shadow_classification(
    convo: dict,
    customer: dict,
    combined,
    *,
    active_draft: dict | None,
    draft_state: str | None,
    verified_name: str | None,
    last_inbound_msg: dict | None,
    turn_id: str | None,
) -> Classification | None:
    """Classify one logical turn, persist + log it, and return the result.

    NEVER raises and NEVER sends a message. In shadow mode the caller ignores the
    return value; it exists so Stage 2 can consume it once routing is enabled.
    """
    s = get_settings()
    if not s.whatsapp_classifier_enabled:
        return None
    try:
        exclude = set(getattr(combined, "fragments", []) or [])
        recent = await _gather_recent_context(convo["id"], exclude)
        facts = await _lifecycle_facts(convo, customer, active_draft, verified_name, recent)
        lifecycle = resolve_lifecycle(facts)

        last_assistant_q = any(
            i.role == "assistant" and (i.text or "").rstrip().endswith("?") for i in recent[-1:]
        )
        state_str = (draft_state or "")
        ci = ClassifierInput(
            message=MessageInput(
                text=combined.text,
                message_type="location" if getattr(combined, "has_location", False) else "text",
                provider_message_id=(last_inbound_msg or {}).get("wa_message_id"),
                has_location=bool(getattr(combined, "has_location", False)),
                timestamp=None,
            ),
            conversation=ConversationInput(
                customer_lifecycle=lifecycle,
                active_order=facts.has_active_order,
                workflow_state=draft_state,
                selected_service=_selected_service(active_draft),
                missing_fields=[],
                human_takeover=(convo.get("status") == "human_takeover"),
                market=(customer or {}).get("market") or "UAE",
                currency=(customer or {}).get("currency") or "AED",
                has_active_slot_options="SLOT" in state_str.upper(),
                last_assistant_was_question=last_assistant_q,
            ),
            recent_context=recent,
            known_signals=KnownSignals(
                known_selection_id=getattr(combined, "selection_id", None),
            ),
        )

        from classifier.service import classify_turn

        classification = await classify_turn(ci, settings=s)
        decision = select_route(classification, ci)

        # persist (idempotent; no-op in sqlite mode)
        try:
            from db.repositories import classifications_repo

            await classifications_repo.insert_classification(
                classification,
                conversation_id=convo.get("id"),
                customer_id=(customer or {}).get("id"),
                message_id=(last_inbound_msg or {}).get("id"),
                provider="evolution",
                provider_message_id=(last_inbound_msg or {}).get("wa_message_id"),
                included_provider_message_ids=[],
                recommended_route=decision.route,
                shadow_mode=s.whatsapp_classifier_shadow_mode,
            )
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            logger.info("classification_persist_skipped", error=str(exc))

        # observability: structured event + usage (same keys services/metrics.py reads)
        logger.info(
            "classification_completed",
            conversation=convo.get("id"),
            classification_version=classification.classification_version,
            classifier_model=classification.classifier_model,
            classifier_status=classification.status,
            primary_intent=classification.primary_intent,
            secondary_intents=classification.secondary_intents,
            service_domain=classification.service_domain,
            confidence=round(classification.intent_confidence, 3),
            recommended_route=decision.route,
            requires_human=classification.requires_human,
            human_reason=classification.human_reason,
            needs_clarification=classification.needs_clarification,
            frustration_level=classification.frustration_level,
            shadow_mode=s.whatsapp_classifier_shadow_mode,
            latency_ms=round(classification.latency_ms, 1),
            input_tokens=classification.tokens_in,
            output_tokens=classification.tokens_out,
            cache_read_tokens=classification.cache_read_tokens,
            cache_creation_tokens=classification.cache_write_tokens,
            cost_usd=round(classification.cost_usd, 6),
            turn=turn_id,
        )
        return classification
    except Exception as exc:  # noqa: BLE001 — classifier must never break the reply path
        logger.warning("classification_error", error=str(exc), turn=turn_id)
        return None
