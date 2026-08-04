"""Replay orchestrator: drive conversations through the real pipeline with
bounded concurrency, rate limiting, retries, a hard cost gate, and resume.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.clock import DUBAI_TZ
from ..core.config import ReplayConfig
from ..core.models import (
    Conversation,
    Direction,
    ModelUsage,
    ReplayConversationResult,
    ReplayTurn,
)
from ..eval import divergence as divergence_mod
from ..eval.evaluator import evaluate_turn
from . import instrument, pipeline
from .grouping import TurnGroup, group_turns
from .isolation import SyntheticIdentity


class RateLimiter:
    """Simple async rate limiter: at most `rpm` acquisitions per rolling minute."""

    def __init__(self, rpm: int) -> None:
        self._min_interval = 60.0 / max(1, rpm)
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_at = max(now, self._next_at) + self._min_interval


class CostGate:
    """Hard stop at the configured ceiling unless explicitly allowed to exceed."""

    def __init__(self, ceiling: float, allow_exceed: bool) -> None:
        self.ceiling = ceiling
        self.allow_exceed = allow_exceed
        self.spent = 0.0
        self.tripped = False
        self._lock = asyncio.Lock()

    async def add(self, cost: float) -> None:
        async with self._lock:
            self.spent += cost
            if not self.allow_exceed and self.ceiling > 0 and self.spent >= self.ceiling:
                self.tripped = True

    def should_stop(self) -> bool:
        return self.tripped and not self.allow_exceed


@dataclass
class RunProgress:
    run_dir: Path
    completed_chat_ids: set[str] = field(default_factory=set)

    @property
    def progress_file(self) -> Path:
        return self.run_dir / "progress.json"

    def load(self) -> None:
        if self.progress_file.is_file():
            try:
                data = json.loads(self.progress_file.read_text(encoding="utf-8"))
                self.completed_chat_ids = set(data.get("completed_chat_ids", []))
            except Exception:  # noqa: BLE001
                self.completed_chat_ids = set()

    def mark(self, chat_id: str) -> None:
        self.completed_chat_ids.add(chat_id)
        self._flush()

    def _flush(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.progress_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"completed_chat_ids": sorted(self.completed_chat_ids)}), encoding="utf-8")
        tmp.replace(self.progress_file)


def _historical_reply_for(group: TurnGroup, next_group: Optional[TurnGroup],
                          outbound: list) -> str:
    """Join staff replies that fall between this turn and the next (by timestamp)."""
    last = group.fragments[-1].timestamp
    nxt = next_group.first.timestamp if next_group else None
    parts = []
    for m in outbound:
        if m.timestamp is None or last is None:
            continue
        if m.timestamp >= last and (nxt is None or m.timestamp < nxt):
            body = (m.text or m.caption or "").strip()
            if body:
                parts.append(body)
    return "\n".join(parts)


def _style_flags(reply: str) -> tuple[bool, bool, bool]:
    """(emoji_present, dash_present, exclaim_present) in the FINAL reply."""
    from ..eval.evaluator import _DASH_RE, _EMOJI_RE, _EXCLAIM_RE

    return (
        bool(_EMOJI_RE.search(reply)) if reply else False,
        bool(_DASH_RE.search(reply)) if reply else False,
        bool(_EXCLAIM_RE.search(reply)) if reply else False,
    )


async def _run_conversation(
    client,
    conv: Conversation,
    identity: SyntheticIdentity,
    cfg: ReplayConfig,
    run_id: str,
    limiter: RateLimiter,
    cost_gate: CostGate,
) -> ReplayConversationResult:
    result = ReplayConversationResult(
        replay_run_id=run_id,
        source_archive=conv.source_archive,
        source_chat_id=conv.source_chat_id,
        source_filename=conv.source_filename,
        synthetic_customer_id=identity.customer_id_label,
        synthetic_conversation_id=f"replay_conv_{conv.source_chat_id}",
        category=conv.category,
        replay_status="running",
        started_at=datetime.now(timezone.utc),
    )

    # Historical-date fidelity: set this task's replay clock to the conversation's
    # first inbound instant (UAE market tz). Async-task-isolated via contextvar.
    if cfg.date_mode == "HISTORICAL_DATE_CONTEXT":
        first = conv.first_inbound_at
        if first is not None:
            instrument.set_replay_now(first.replace(tzinfo=DUBAI_TZ))
    else:
        instrument.clear_replay_now()

    sink = pipeline.capture_channel.get_sink()
    sink.set_context(identity.context_key)

    groups = group_turns(conv.messages)
    outbound = conv.outbound_messages
    result.historical_outbound_count = len(outbound)

    prev_turn: Optional[ReplayTurn] = None
    prev_reply = ""
    for idx, group in enumerate(groups):
        next_group = groups[idx + 1] if idx + 1 < len(groups) else None
        await limiter.acquire()

        tr = await _run_turn_with_retries(client, group, identity, cfg)

        usage, tool_caps = pipeline.usage_from_records(tr.llm_records)
        await cost_gate.add(usage.estimated_cost_usd)

        media = group.media_message
        turn = ReplayTurn(
            source_chat_id=conv.source_chat_id,
            turn_index=idx,
            customer_message=group.combined_text or (media.caption if media else ""),
            customer_fragments=[(m.text or m.caption or "") for m in group.fragments],
            agent_reply=tr.reply_text,
            raw_model_response=(tr.llm_records[-1].text if tr.llm_records else tr.reply_text),
            historical_reply=_historical_reply_for(group, next_group, outbound),
            media_type=(media.message_type.value if media else ""),
            media_available=(media.media_available if media else True),
            tool_calls=tool_caps,
            usage=usage,
            error=tr.error,
        )
        # Workflow snapshot -> turn fields.
        snap = tr.snapshot
        turn.order_state_after = snap.order_state
        turn.order_state_before = prev_turn.order_state_after if prev_turn else ""
        turn.resolved_service = snap.service
        turn.service_code = snap.service_code
        turn.pickup_slot_options = []  # populated when a slots tool is captured
        turn.selected_pickup_slot = snap.pickup_slot
        turn.facility_selection_result = snap.facility_result
        turn.final_total = snap.final_total
        turn.pre_discount_total = snap.pre_discount_total
        turn.discount_amount = snap.discount_amount
        turn.discount_percentage = snap.discount_percentage
        turn.additional_notes = snap.additional_notes
        turn.confirmation_status = snap.confirmation_status
        turn.human_intervention_status = snap.conversation_status
        turn.catalogue_version = snap.catalogue_version
        # Slot options from tool calls, if any.
        for tc in tool_caps:
            if tc.tool_name in ("get_pickup_slots", "list_pickup_slots"):
                turn.pickup_slot_options = [str(tc.safe_result_summary)[:120]]

        # Style analysis.
        turn.response_word_count = len(turn.agent_reply.split())
        turn.response_character_count = len(turn.agent_reply)
        emoji_p, dash_p, excl_p = _style_flags(turn.agent_reply)
        turn.emoji_removed = not emoji_p
        turn.dash_normalized = not dash_p
        turn.exclamation_normalized = not excl_p

        # Evaluation + divergence.
        turn.findings = evaluate_turn(turn, {"prev_reply": prev_reply})
        turn.divergence = divergence_mod.detect(prev_turn, turn)

        result.turns.append(turn)
        prev_turn = turn
        if turn.agent_reply:
            prev_reply = turn.agent_reply

        if cost_gate.should_stop():
            result.error = "cost_ceiling_reached"
            break

    sink.clear_context()
    instrument.clear_replay_now()

    # Conversation rollups.
    if result.turns:
        last_state = next((t.order_state_after for t in reversed(result.turns) if t.order_state_after), "")
        result.final_order_state = last_state
        result.order_confirmed = any(t.confirmation_status == "confirmed" for t in result.turns)
    result.replay_status = "failed" if all(t.error for t in result.turns) and result.turns else "completed"
    result.completed_at = datetime.now(timezone.utc)
    return result


async def _run_turn_with_retries(client, group: TurnGroup, identity: SyntheticIdentity,
                                 cfg: ReplayConfig):
    attempts = 0
    last = None
    while attempts <= cfg.max_retries:
        tr = await pipeline.run_turn(client, group, identity.phone, identity.name, identity.context_key)
        last = tr
        if not tr.error:
            return tr
        attempts += 1
        # Exponential backoff with jitter for transient webhook/API errors.
        await asyncio.sleep(min(8.0, (2 ** attempts) * 0.5) + random.random() * 0.3)
    return last


@dataclass
class RunOutcome:
    run_id: str
    results: list[ReplayConversationResult]
    stopped_for_cost: bool
    total_cost: float
    skipped_resumed: int


async def run_replay(
    conversations: list[Conversation],
    identities: dict[str, SyntheticIdentity],
    cfg: ReplayConfig,
    run_id: str,
    run_dir: Path,
    *,
    resume: bool = False,
    on_result=None,
) -> RunOutcome:
    """Run the replay over the given conversations. Persists progress + results
    incrementally so the run can resume after interruption."""
    progress = RunProgress(run_dir=run_dir)
    if resume:
        progress.load()

    limiter = RateLimiter(cfg.requests_per_minute)
    cost_gate = CostGate(cfg.max_cost_usd, cfg.allow_exceed_cost_ceiling)
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))
    # Historical-date mode uses a per-task contextvar clock, so concurrency is
    # safe; keep it as configured.

    todo = [c for c in conversations if c.source_chat_id not in progress.completed_chat_ids]
    skipped_resumed = len(conversations) - len(todo)
    results: list[ReplayConversationResult] = []
    results_lock = asyncio.Lock()

    async with pipeline.app_context() as client:
        async def worker(conv: Conversation):
            if cost_gate.should_stop():
                return
            identity = identities[conv.source_chat_id]
            async with sem:
                if cost_gate.should_stop():
                    return
                try:
                    res = await _run_conversation(
                        client, conv, identity, cfg, run_id, limiter, cost_gate
                    )
                except Exception as exc:  # noqa: BLE001 - one bad chat must not kill the run
                    res = ReplayConversationResult(
                        replay_run_id=run_id, source_archive=conv.source_archive,
                        source_chat_id=conv.source_chat_id, source_filename=conv.source_filename,
                        synthetic_customer_id=identity.customer_id_label,
                        synthetic_conversation_id=f"replay_conv_{conv.source_chat_id}",
                        category=conv.category, replay_status="failed",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc), error=str(exc),
                    )
            async with results_lock:
                results.append(res)
                progress.mark(conv.source_chat_id)
                if on_result is not None:
                    on_result(res)

        # Bounded concurrency via the semaphore inside each worker; gather all.
        await asyncio.gather(*(worker(c) for c in todo))

    return RunOutcome(
        run_id=run_id,
        results=results,
        stopped_for_cost=cost_gate.should_stop(),
        total_cost=cost_gate.spent,
        skipped_resumed=skipped_resumed,
    )
