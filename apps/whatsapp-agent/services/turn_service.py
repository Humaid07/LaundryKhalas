"""Per-conversation inbound buffer: debounce timer + conversation lock + flush.

Ties the durable turn model (``db.repositories.turns_repo``) to the pure
aggregation logic (``services.message_aggregation``) and an injected *processor*
that turns one combined turn into one agent reply (task spec §§15-27).

Flow per inbound fragment:
  1. The webhook stored + deduped the raw message and linked it to the open turn
     (``repo.append_or_open``), extending the aggregation deadline.
  2. ``schedule`` (re)arms a single in-process debounce task for that
     conversation — each new fragment cancels the prior timer and re-arms it, so
     we wait for a lull before processing (spec §15).
  3. When the timer fires, ``flush`` runs under a per-conversation asyncio lock,
     optimistically claims the turn (``repo.claim_for_processing`` — a
     conversation-level lock so two workers never process the same turn, spec
     §17), combines the fragments and calls the processor ONCE.

Restart recovery: ``recover`` re-drives any turn left open/in-flight by a crash
(spec §§21/27). Timers are in-process (single-worker assumption); cross-process
safety comes from the DB claim. Dependencies are injected so the whole thing is
unit-testable with an in-memory fake repo + fake processor + a controllable clock.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from services import message_aggregation as agg

logger = structlog.get_logger(__name__)

# The processor is: async (conversation_id, CombinedTurn, turn_row) -> response id|None
Processor = "collections.abc.Callable"


def _fragment_view(message_row: dict) -> dict:
    """Map a stored message row back to the fragment shape combine_fragments
    expects. Selection/location were saved in the message metadata at ingest so a
    turn can be reconstructed from the DB after a restart (spec §21)."""
    meta = message_row.get("metadata") or {}
    if isinstance(meta, str):  # asyncpg may hand back jsonb as text in some paths
        import json
        try:
            meta = json.loads(meta)
        except Exception:  # noqa: BLE001
            meta = {}
    return {
        "text": message_row.get("message_text") or "",
        "selection_id": meta.get("selection_id"),
        "latitude": meta.get("latitude"),
        "longitude": meta.get("longitude"),
    }


class TurnBuffer:
    def __init__(self, repo, *, debounce_seconds: float, max_seconds: float,
                 now_fn=None, sleep_fn=None):
        self.repo = repo
        self.debounce = float(debounce_seconds)
        self.max = float(max_seconds)
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep_fn or asyncio.sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _lock(self, conversation_id: str) -> asyncio.Lock:
        lock = self._locks.get(conversation_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[conversation_id] = lock
        return lock

    def deadline_for(self, message_at: datetime) -> datetime:
        from datetime import timedelta
        return message_at + timedelta(seconds=self.debounce)

    def hard_cap_for(self, message_at: datetime) -> datetime:
        from datetime import timedelta
        return message_at + timedelta(seconds=self.max)

    async def add_fragment(self, conversation_id: str, customer_id: str | None, *,
                           message_id: str | None, message_at: datetime,
                           debounce_seconds: float | None = None) -> dict:
        """Append a fragment to (or open) the conversation's turn. Returns the
        turn row. Different conversations use INDEPENDENT turns/timers/locks, so
        two customers never share a buffer (spec §17).

        ``debounce_seconds`` is the ADAPTIVE per-fragment inactivity wait chosen by
        the caller from the message-completeness classifier (falls back to the
        buffer default). The turn's deadline is always capped at first_message_at +
        ``self.max`` so continuous slow fragments can't postpone processing past
        the hard aggregation window."""
        from datetime import timedelta
        debounce = self.debounce if debounce_seconds is None else max(0.0, float(debounce_seconds))
        # Serialize ingestion per conversation so two fragments racing in
        # separate webhook calls can't each open a duplicate turn (spec §17).
        async with self._lock(conversation_id):
            turn, opened = await self.repo.append_or_open(
                conversation_id, customer_id,
                message_id=message_id, message_at=message_at,
                deadline_at=message_at + timedelta(seconds=debounce),
                first_deadline_at=self.hard_cap_for(message_at),
                max_seconds=self.max,
            )
        logger.info("customer_turn_buffered" if not opened else "customer_turn_created",
                    conversation=conversation_id, turn=turn.get("turn_id"),
                    message_count=turn.get("message_count"))
        return turn

    def schedule(self, conversation_id: str, turn: dict, processor) -> None:
        """(Re)arm the debounce timer for a conversation. Cancels any prior timer
        so the newest fragment's deadline wins (spec §15 — the timer resets)."""
        old = self._tasks.get(conversation_id)
        if old is not None and not old.done():
            old.cancel()
            logger.info("customer_turn_debounce_reset", conversation=conversation_id)
        deadline = turn.get("aggregation_deadline_at")
        self._tasks[conversation_id] = asyncio.create_task(
            self._wait_and_flush(conversation_id, deadline, processor))

    async def _wait_and_flush(self, conversation_id: str, deadline: datetime, processor) -> None:
        try:
            if deadline is not None:
                delay = (deadline - self._now()).total_seconds()
                if delay > 0:
                    await self._sleep(delay)
            await self.flush(conversation_id, processor)
        except asyncio.CancelledError:  # a newer fragment re-armed the timer
            return
        except Exception as exc:  # noqa: BLE001 — a timer must never crash the loop
            logger.warning("customer_turn_timer_failed", conversation=conversation_id, error=str(exc))
        finally:
            if self._tasks.get(conversation_id) is asyncio.current_task():
                self._tasks.pop(conversation_id, None)

    async def flush(self, conversation_id: str, processor) -> dict | None:
        """Process the conversation's open turn ONCE. Safe to call concurrently /
        repeatedly: the per-conversation lock + optimistic DB claim guarantee a
        single processing (spec §§9/17)."""
        # Hold the conversation lock ONLY to atomically pick + claim the open turn
        # (fast). The claim ('processing') is the real single-processing guard, so
        # the slow processor runs OUTSIDE the lock — a fragment arriving mid-flush
        # never blocks the webhook, and simply opens the NEXT turn (spec §§17/21).
        async with self._lock(conversation_id):
            turn = await self.repo.get_open_turn(conversation_id)
            if turn is None:
                return None
            claimed = await self.repo.claim_for_processing(turn["id"])
            if claimed is None:
                logger.info("customer_turn_already_claimed", conversation=conversation_id)
                return None
            turn = claimed
            rows = await self.repo.fragments(turn["turn_id"])

        combined = agg.combine_fragments([_fragment_view(r) for r in rows])
        logger.info("customer_turn_processing_started", conversation=conversation_id,
                    turn=turn["turn_id"], message_count=combined.message_count)
        try:
            response_id = await processor(conversation_id, combined, turn)
        except Exception as exc:  # noqa: BLE001
            await self.repo.mark_failed(turn["id"])
            logger.warning("customer_turn_processing_failed", conversation=conversation_id,
                           turn=turn["turn_id"], error=str(exc))
            raise
        await self.repo.mark_completed(
            turn["id"], combined_text=combined.text,
            response_message_id=str(response_id) if response_id else None)
        logger.info("customer_turn_processing_completed", conversation=conversation_id,
                    turn=turn["turn_id"], message_count=combined.message_count)
        return turn

    async def cancel(self, conversation_id: str) -> None:
        """Drop a conversation's open turn + timer (e.g. human takeover began, so
        the AI must not fire a delayed reply — spec §24). Fragments stay stored."""
        task = self._tasks.pop(conversation_id, None)
        if task is not None and not task.done():
            task.cancel()
        await self.repo.cancel_open_turns(conversation_id)

    async def recover(self, processor) -> int:
        """Re-drive turns left open/in-flight by a restart (spec §§21/27). Returns
        the number of turns flushed. A turn stuck in 'processing' is released back
        to pending first so it can be reclaimed."""
        pending = await self.repo.recoverable_turns()
        count = 0
        for turn in pending:
            if turn.get("status") == "processing":
                await self.repo.release_to_pending(turn["id"])
            try:
                if await self.flush(turn["conversation_id"], processor):
                    count += 1
            except Exception as exc:  # noqa: BLE001 — recovery must not crash startup
                logger.warning("customer_turn_recovery_failed",
                               conversation=turn.get("conversation_id"), error=str(exc))
        logger.info("customer_turn_recovery_done", recovered=count)
        return count
