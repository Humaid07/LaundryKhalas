"""Persistence for WhatsApp intent classifications (Supabase mode only).

Writes one row per classified logical turn to ``whatsapp_message_classifications``
(migration 000039). Insert is idempotent on
(provider, provider_message_id, classification_version) via ``on conflict do
nothing`` backing the table's unique constraint — a retried webhook never
double-inserts.

Every function is a NO-OP (returns None / []) when the backend is in SQLite mode,
so the offline test suite and local dev never touch asyncpg. Callers additionally
wrap these in try/except (the classifier must never break the reply path).
"""
from __future__ import annotations

import json

from db import database
from classifier.schema import Classification
from classifier.router import RouteDecision

_RETURN_COLS = """
    id, conversation_id, customer_id, message_id, provider, provider_message_id,
    classification_version, classifier_model, classifier_status, primary_intent,
    secondary_intents, intent_confidence, service_domain, service_subtype,
    service_confidence, customer_goal, conversation_route, recommended_route,
    fixed_template_id, pricing_intent, payment_intent, repair_intent,
    complaint_type, sentiment, frustration_level, urgency, requires_human,
    human_reason, needs_clarification, clarification_topic, should_cancel_followups,
    reason_codes, detected_entities, shadow_mode, latency_ms, input_tokens,
    output_tokens, cache_creation_tokens, cache_read_tokens, estimated_cost,
    corrected_primary_intent, corrected_service_domain, corrected_complaint_type,
    corrected_human_label, corrected_by, corrected_at, correction_reason, created_at
"""


async def insert_classification(
    c: Classification,
    *,
    conversation_id: str | None,
    customer_id: str | None,
    message_id: str | None,
    provider: str,
    provider_message_id: str | None,
    included_provider_message_ids: list[str] | None = None,
    recommended_route: str | None = None,
    shadow_mode: bool = True,
) -> dict | None:
    """Idempotently persist one classification. No-op (None) in SQLite mode."""
    if not database.is_supabase_mode():
        return None
    row = await database.fetchrow(
        f"""
        insert into whatsapp_message_classifications
            (conversation_id, customer_id, message_id, provider, provider_message_id,
             included_provider_message_ids, classification_version, classifier_model,
             classifier_status, primary_intent, secondary_intents, intent_confidence,
             service_domain, service_subtype, service_confidence, customer_goal,
             conversation_route, recommended_route, fixed_template_id, pricing_intent,
             payment_intent, repair_intent, complaint_type, sentiment, frustration_level,
             urgency, requires_human, human_reason, needs_clarification, clarification_topic,
             should_cancel_followups, reason_codes, detected_entities, shadow_mode,
             latency_ms, input_tokens, output_tokens, cache_creation_tokens,
             cache_read_tokens, estimated_cost, is_test_data, is_demo, environment, created_by_seed)
        values
            ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
             $21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33::jsonb,$34,$35,$36,$37,
             $38,$39,$40,false,false,'dev',false)
        on conflict (provider, provider_message_id, classification_version) do nothing
        returning {_RETURN_COLS}
        """,
        conversation_id,
        customer_id,
        message_id,
        provider,
        provider_message_id,
        included_provider_message_ids or [],
        c.classification_version,
        c.classifier_model,
        c.status,
        c.primary_intent,
        list(c.secondary_intents),
        c.intent_confidence,
        c.service_domain,
        c.service_subtype,
        c.service_confidence,
        c.customer_goal,
        c.conversation_route,
        recommended_route,
        c.fixed_template_id,
        c.pricing_intent,
        c.payment_intent,
        c.repair_intent,
        c.complaint_type,
        c.sentiment,
        c.frustration_level,
        c.urgency,
        c.requires_human,
        c.human_reason,
        c.needs_clarification,
        c.clarification_topic,
        c.should_cancel_followups,
        list(c.reason_codes),
        json.dumps(c.detected_entities.as_dict()),
        shadow_mode,
        int(round(c.latency_ms)),
        c.tokens_in,
        c.tokens_out,
        c.cache_write_tokens,
        c.cache_read_tokens,
        c.cost_usd,
    )
    return row


async def get_for_conversation(conversation_id: str, *, limit: int = 50) -> list[dict]:
    if not database.is_supabase_mode():
        return []
    return await database.fetch(
        f"select {_RETURN_COLS} from whatsapp_message_classifications "
        "where conversation_id = $1 order by created_at desc limit $2",
        conversation_id,
        limit,
    )


async def get_by_id(classification_id: str) -> dict | None:
    if not database.is_supabase_mode():
        return None
    return await database.fetchrow(
        f"select {_RETURN_COLS} from whatsapp_message_classifications where id = $1",
        classification_id,
    )


async def add_correction(
    classification_id: str,
    *,
    corrected_by: str,
    primary_intent: str | None = None,
    service_domain: str | None = None,
    complaint_type: str | None = None,
    human_label: str | None = None,
    reason: str | None = None,
) -> dict | None:
    """Store an Operations correction WITHOUT destroying the original result
    (spec). Only the corrected_* columns are written."""
    if not database.is_supabase_mode():
        return None
    return await database.fetchrow(
        f"""
        update whatsapp_message_classifications
           set corrected_primary_intent = coalesce($2, corrected_primary_intent),
               corrected_service_domain  = coalesce($3, corrected_service_domain),
               corrected_complaint_type  = coalesce($4, corrected_complaint_type),
               corrected_human_label     = coalesce($5, corrected_human_label),
               correction_reason         = coalesce($6, correction_reason),
               corrected_by              = $7,
               corrected_at              = now()
         where id = $1
        returning {_RETURN_COLS}
        """,
        classification_id,
        primary_intent,
        service_domain,
        complaint_type,
        human_label,
        reason,
        corrected_by,
    )


def build_decision_route(decision: RouteDecision | None) -> str | None:
    """Small helper so the hook can pass the validated router route without
    importing RouteDecision internals."""
    return decision.route if decision else None
