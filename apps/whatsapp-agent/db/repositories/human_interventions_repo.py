"""Human-intervention (abuse/threat takeover) persistence — dev/test Supabase.

The AI pause reuses the existing ``conversations.status = 'human_takeover'`` gate
(the webhook stores-only for those). This repo owns the RICH lifecycle:
idempotent create (one active event per conversation), concurrency-safe claim,
resolve, release-to-AI, the Operations queue read, and metrics.

Idempotency + concurrency are enforced in SQL:
  * ``create_and_pause`` runs INSERT(intervention) + UPDATE(conversation pause) in
    ONE transaction; the partial-unique index (one active row per conversation)
    makes re-processing the same abusive turn / a duplicate webhook a no-op that
    returns the existing event.
  * ``claim`` is an atomic ``UPDATE … WHERE assigned_agent_id IS NULL RETURNING``
    so two agents can never both take the same conversation.

PII-safe: no phone/address/email stored here (only a sanitized preview).
"""
from __future__ import annotations

import json

from db import database

_TERMINAL = ("RESOLVED", "RELEASED_TO_AI", "CLOSED")


async def get_active(conversation_id: str) -> dict | None:
    return await database.fetchrow(
        "select * from human_interventions "
        "where conversation_id = $1 and takeover_status <> all($2::text[]) "
        "order by flagged_at desc limit 1",
        conversation_id, list(_TERMINAL),
    )


async def get(intervention_id: str) -> dict | None:
    return await database.fetchrow(
        "select * from human_interventions where id = $1", intervention_id)


async def abuse_event_count(conversation_id: str) -> int:
    """How many abuse/threat interventions this conversation has already produced
    (for REPEATED_ABUSE / SEVERE_HOSTILITY escalation across turns)."""
    return int(await database.fetchval(
        "select count(*) from human_interventions "
        "where conversation_id = $1 and takeover_reason in ('ABUSIVE_LANGUAGE','THREAT')",
        conversation_id,
    ) or 0)


async def create_and_pause(
    conversation_id: str, *, reason: str, abuse_category: str | None,
    abuse_target: str | None, threat_severity: str | None, internal_priority: str,
    confidence: float | None, reason_codes: list[str], flagged_message_id: str | None,
    flagged_turn_id: str | None, sanitized_preview: str | None,
) -> tuple[dict, bool]:
    """Atomically (one transaction): create the active intervention (or return the
    existing one) AND pause the conversation (status→human_takeover). Returns
    (intervention_row, created). ``created`` is False when an active event already
    existed — the caller must then NOT send a second holding message unless the
    notice was never sent."""
    pool = await database.get_pool()
    async with pool.acquire() as con:
        async with con.transaction():
            existing = await con.fetchrow(
                "select * from human_interventions "
                "where conversation_id = $1 and takeover_status <> all($2::text[]) "
                "for update",
                conversation_id, list(_TERMINAL),
            )
            if existing:
                return dict(existing), False
            row = await con.fetchrow(
                """
                insert into human_interventions
                    (conversation_id, takeover_status, takeover_reason, abuse_category,
                     abuse_target, threat_severity, confidence, reason_codes,
                     internal_priority, flagged_message_id, flagged_turn_id,
                     sanitized_preview, automation_paused, is_test_data, environment)
                values ($1,'WAITING_FOR_HUMAN',$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,true,false,'dev')
                returning *
                """,
                conversation_id, reason, abuse_category, abuse_target, threat_severity,
                confidence, json.dumps(reason_codes or []), internal_priority,
                flagged_message_id, flagged_turn_id, sanitized_preview,
            )
            # Pause the conversation via the existing gate + record why.
            await con.execute(
                """
                update conversations
                   set status = 'human_takeover',
                       human_intervention_required = true,
                       priority = $2,
                       handoff_reason = $3,
                       takeover_reason = $3,
                       takeover_status = 'WAITING_FOR_HUMAN'
                 where id = $1
                """,
                conversation_id, _priority_to_convo(internal_priority), reason,
            )
            return dict(row), True


def _priority_to_convo(internal_priority: str) -> str:
    return {"CRITICAL": "urgent", "HIGH": "high", "MEDIUM": "medium"}.get(
        internal_priority, "low")


async def mark_notice_sent(intervention_id: str) -> dict | None:
    return await database.fetchrow(
        "update human_interventions set customer_notice_sent = true, "
        "customer_notified_at = now() where id = $1 and customer_notice_sent = false "
        "returning *",
        intervention_id,
    )


async def claim(intervention_id: str, *, agent_id: str, agent_name: str | None) -> dict | None:
    """Concurrency-safe claim. Returns the row on success, None if it was already
    claimed / not claimable (the caller returns a 409 conflict)."""
    return await database.fetchrow(
        """
        update human_interventions
           set assigned_agent_id = $2, assigned_agent_name = $3,
               takeover_status = 'HUMAN_ACTIVE', accepted_at = coalesce(accepted_at, now())
         where id = $1
           and assigned_agent_id is null
           and takeover_status in ('WAITING_FOR_HUMAN','ASSIGNED')
        returning *
        """,
        intervention_id, agent_id, agent_name,
    )


async def mark_human_active(conversation_id: str) -> None:
    await database.execute(
        "update human_interventions set takeover_status = 'HUMAN_ACTIVE' "
        "where conversation_id = $1 and takeover_status in ('WAITING_FOR_HUMAN','ASSIGNED')",
        conversation_id,
    )


async def resolve(intervention_id: str, *, agent_id: str, resolution_reason: str | None,
                  close: bool = False) -> dict | None:
    status = "CLOSED" if close else "RESOLVED"
    return await database.fetchrow(
        "update human_interventions set takeover_status = $2, resolution_reason = $3, "
        "resolved_at = now() where id = $1 and takeover_status <> all($4::text[]) returning *",
        intervention_id, status, resolution_reason, list(_TERMINAL),
    )


async def release_to_ai(intervention_id: str) -> dict | None:
    return await database.fetchrow(
        "update human_interventions set takeover_status = 'RELEASED_TO_AI', "
        "automation_paused = false, released_to_ai_at = now() "
        "where id = $1 and takeover_status <> all($2::text[]) returning *",
        intervention_id, list(_TERMINAL),
    )


# --- Operations queue read (PII-safe: masked phone + sanitized preview) ------
_QUEUE_SELECT = """
  select hi.id, hi.conversation_id, hi.takeover_status, hi.takeover_reason,
         hi.abuse_category, hi.threat_severity, hi.internal_priority,
         hi.assigned_agent_id, hi.assigned_agent_name, hi.customer_notice_sent,
         hi.flagged_at, hi.accepted_at, hi.resolved_at, hi.released_to_ai_at,
         hi.sanitized_preview,
         cust.display_name  as customer_name,
         cust.masked_phone  as masked_phone,
         cust.market        as market,
         c.linked_order_id  as linked_order_id,
         c.unread_count     as unread_count,
         c.status           as conversation_status
    from human_interventions hi
    join conversations c on c.id = hi.conversation_id
    left join customers cust on cust.id = c.customer_id
"""

_PRIORITY_RANK = "case hi.internal_priority when 'CRITICAL' then 0 when 'HIGH' then 1 " \
                 "when 'MEDIUM' then 2 else 3 end"


async def list_queue(*, status: str | None = None, reason: str | None = None,
                     severity: str | None = None, assigned_agent_id: str | None = None,
                     market: str | None = None, active_only: bool = True) -> list[dict]:
    where = []
    args: list = []
    if active_only and not status:
        where.append(f"hi.takeover_status <> all(${len(args) + 1}::text[])")
        args.append(list(_TERMINAL))
    if status:
        where.append(f"hi.takeover_status = ${len(args) + 1}")
        args.append(status)
    if reason:
        where.append(f"hi.takeover_reason = ${len(args) + 1}")
        args.append(reason)
    if severity:
        where.append(f"hi.threat_severity = ${len(args) + 1}")
        args.append(severity)
    if assigned_agent_id:
        where.append(f"hi.assigned_agent_id = ${len(args) + 1}")
        args.append(assigned_agent_id)
    if market:
        where.append(f"lower(cust.market) = lower(${len(args) + 1})")
        args.append(market)
    clause = (" where " + " and ".join(where)) if where else ""
    return await database.fetch(
        _QUEUE_SELECT + clause + f" order by {_PRIORITY_RANK}, hi.flagged_at asc", *args)


async def metrics() -> dict:
    row = await database.fetchrow(
        """
        select
          count(*)                                                          as total,
          count(*) filter (where takeover_status = 'WAITING_FOR_HUMAN')     as waiting,
          count(*) filter (where takeover_status = 'HUMAN_ACTIVE')          as human_active,
          count(*) filter (where takeover_status = 'RESOLVED')              as resolved,
          count(*) filter (where takeover_status = 'RELEASED_TO_AI')        as released_to_ai,
          count(*) filter (where takeover_reason = 'THREAT')                as threats,
          count(*) filter (where takeover_reason = 'ABUSIVE_LANGUAGE')      as abusive,
          count(*) filter (where internal_priority = 'CRITICAL')            as critical,
          avg(extract(epoch from (accepted_at - flagged_at))) filter (where accepted_at is not null)
                                                                            as avg_seconds_to_accept
        from human_interventions
        """
    )
    d = dict(row or {})
    if d.get("avg_seconds_to_accept") is not None:
        d["avg_seconds_to_accept"] = round(float(d["avg_seconds_to_accept"]), 1)
    return d
