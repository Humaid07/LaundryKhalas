"""Durable conversation-turn model (task spec §§15/17/18/21/27).

A "conversation turn" groups the rapid inbound fragments a customer sends as one
thought ("Hi" / "need wash" / "tomorrow") so the agent processes them together
and replies ONCE. Each raw message row still exists (per-message wa_message_id
dedup + audit); a turn links them via ``messages.turn_id`` and carries the
aggregation window + processing status so an in-flight turn survives a restart.

asyncpg / Supabase only — mirrors the other repos. The in-process debounce
timer + per-conversation lock live in ``services.turn_service``; this module is
just the durable state.

Status lifecycle: pending -> aggregating -> processing -> completed | failed.
(cancelled is available for takeover/abandon.)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from db import database

OPEN_STATUSES = ("pending", "aggregating")
# 'processing' is included when recovering after a crash — a turn stuck in
# processing (its worker died) must be retryable.
RECOVERABLE_STATUSES = ("pending", "aggregating", "processing")


def _new_turn_id() -> str:
    return f"turn_{uuid.uuid4().hex[:20]}"


async def get_open_turn(conversation_id: str) -> dict | None:
    """The current open (pending/aggregating) turn for a conversation, if any."""
    return await database.fetchrow(
        "select * from conversation_turns where conversation_id = $1 "
        "and status = any($2::text[]) order by created_at desc limit 1",
        conversation_id, list(OPEN_STATUSES),
    )


async def append_or_open(
    conversation_id: str, customer_id: str | None, *,
    message_id: str | None, message_at: datetime,
    deadline_at: datetime, first_deadline_at: datetime,
    max_seconds: float | None = None,
) -> tuple[dict, bool]:
    """Add a fragment to the open turn, or open a new one. Returns (turn, opened).

    ``deadline_at`` is the (adaptive) debounce deadline for THIS fragment
    (last + debounce); ``first_deadline_at`` is the hard cap used when opening a
    new turn. When ``max_seconds`` is given, an APPEND caps the new deadline at
    ``first_message_at + max_seconds`` so the maximum aggregation window from the
    FIRST fragment is preserved and continuous slow fragments can't postpone
    processing indefinitely. Links ``message_id`` to the turn (messages.turn_id).
    """
    existing = await get_open_turn(conversation_id)
    if existing is not None:
        row = await database.fetchrow(
            "update conversation_turns set "
            "  status = 'aggregating', "
            "  last_message_at = $2, "
            "  aggregation_deadline_at = case when $4::double precision is null then $3 "
            "     else least($3, first_message_at + make_interval(secs => $4::double precision)) end, "
            "  message_count = message_count + 1, "
            "  updated_at = now() "
            "where id = $1 returning *",
            existing["id"], message_at, deadline_at, max_seconds,
        )
        if message_id:
            await link_message(message_id, row["turn_id"])
        return row, False

    turn_id = _new_turn_id()
    # The new turn's deadline is the earlier of its own debounce and its hard cap.
    deadline = min(deadline_at, first_deadline_at)
    row = await database.fetchrow(
        "insert into conversation_turns "
        "  (turn_id, conversation_id, customer_id, direction, status, "
        "   first_message_at, last_message_at, aggregation_deadline_at, message_count) "
        "values ($1, $2, $3, 'inbound', 'pending', $4, $4, $5, 1) returning *",
        turn_id, conversation_id, customer_id, message_at, deadline,
    )
    if message_id:
        await link_message(message_id, turn_id)
    return row, True


async def link_message(message_id: str, turn_id: str) -> None:
    await database.execute(
        "update messages set turn_id = $2 where id = $1 and turn_id is null",
        message_id, turn_id,
    )


async def claim_for_processing(turn_pk: str) -> dict | None:
    """Optimistically move a turn to 'processing' (conversation-level lock via a
    guarded UPDATE). Returns the row if THIS worker won the claim, else None — so
    two workers can never process the same turn (spec §17)."""
    return await database.fetchrow(
        "update conversation_turns set status = 'processing', updated_at = now() "
        "where id = $1 and status = any($2::text[]) returning *",
        turn_pk, list(OPEN_STATUSES),
    )


async def fragments(turn_id: str) -> list[dict]:
    """The individual customer message rows in this turn, chronological (spec
    §§17/19). Each keeps its own wa_message_id; combined by message_aggregation."""
    return await database.fetch(
        "select * from messages where turn_id = $1 and sender_type = 'customer' "
        "order by created_at asc",
        turn_id,
    )


async def mark_completed(turn_pk: str, *, combined_text: str,
                         response_message_id: str | None = None,
                         llm_request_id: str | None = None) -> None:
    await database.execute(
        "update conversation_turns set status = 'completed', combined_text = $2, "
        "response_message_id = $3, llm_request_id = $4, processed_at = now(), "
        "updated_at = now() where id = $1",
        turn_pk, combined_text, response_message_id, llm_request_id,
    )


async def mark_failed(turn_pk: str) -> None:
    await database.execute(
        "update conversation_turns set status = 'failed', attempts = attempts + 1, "
        "updated_at = now() where id = $1",
        turn_pk,
    )


async def release_to_pending(turn_pk: str) -> None:
    """Return a claimed turn to pending (e.g. a transient failure to retry)."""
    await database.execute(
        "update conversation_turns set status = 'pending', updated_at = now() "
        "where id = $1 and status = 'processing'",
        turn_pk,
    )


async def cancel_open_turns(conversation_id: str) -> None:
    """Cancel any open turns (e.g. human takeover began). Fragments are kept."""
    await database.execute(
        "update conversation_turns set status = 'cancelled', updated_at = now() "
        "where conversation_id = $1 and status = any($2::text[])",
        conversation_id, list(OPEN_STATUSES),
    )


async def due_turns(now: datetime | None = None) -> list[dict]:
    """Open turns whose aggregation deadline has passed — the startup-recovery /
    sweep set (spec §§21/27: pending turns survive a restart)."""
    now = now or datetime.now(timezone.utc)
    return await database.fetch(
        "select * from conversation_turns where status = any($1::text[]) "
        "and aggregation_deadline_at is not null and aggregation_deadline_at <= $2 "
        "order by aggregation_deadline_at asc",
        list(OPEN_STATUSES), now,
    )


async def recoverable_turns() -> list[dict]:
    """All not-yet-completed turns (pending/aggregating/processing) — used on
    startup to re-drive anything interrupted mid-flight (spec §§21/27)."""
    return await database.fetch(
        "select * from conversation_turns where status = any($1::text[]) "
        "order by first_message_at asc",
        list(RECOVERABLE_STATUSES),
    )
