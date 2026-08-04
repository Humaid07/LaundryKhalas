"""Runtime instrumentation of the real pipeline for replay.

Two hooks, both async-task-isolated via ContextVars so concurrent conversations
never interfere:

1. Clock override — patches `services.clock.now`/`today` to consult a per-task
   replay instant (HISTORICAL_DATE_CONTEXT). The agent already routes ALL
   now/today/relative-date decisions through services.clock, so this is the one
   correct injection point; when no instant is set the real wall clock is used
   (CURRENT_DATE_CONTEXT).

2. LLM usage capture — wraps `llm.service.complete_with_tools` / `complete` to
   append each LLMResult (usage, tool calls, cost, latency, stop reason) to a
   per-task list, so the runner can attribute full technical capture to the
   exact turn without changing any pipeline code.

`install()` is idempotent; `uninstall()` restores originals (used by tests).
"""
from __future__ import annotations

import contextvars
import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Optional

# Per-task replay clock instant (tz-aware) or None (use real wall clock).
_REPLAY_NOW: contextvars.ContextVar[Optional[_dt.datetime]] = contextvars.ContextVar(
    "replay_now", default=None
)

# Per-task list collecting LLM call records for the CURRENT turn.
_LLM_RECORDS: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "replay_llm_records", default=None
)

_installed = False
_orig: dict[str, Any] = {}


@dataclass
class LLMCallRecord:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cache_read: int
    cache_write: int
    cost_usd: float
    latency_ms: float
    stop_reason: str
    tool_rounds: int
    success: bool
    error: str = ""
    tool_calls: list = field(default_factory=list)  # list[ToolCall]


# --- clock context ---------------------------------------------------------
def set_replay_now(instant: Optional[_dt.datetime]) -> None:
    _REPLAY_NOW.set(instant)


def clear_replay_now() -> None:
    _REPLAY_NOW.set(None)


# --- llm capture context ---------------------------------------------------
def begin_turn_capture() -> list:
    records: list = []
    _LLM_RECORDS.set(records)
    return records


def end_turn_capture() -> list:
    records = _LLM_RECORDS.get() or []
    _LLM_RECORDS.set(None)
    return records


def install() -> None:
    global _installed
    if _installed:
        return

    # 1) clock
    from services import clock as _clock

    _orig["clock.now"] = _clock.now
    _orig["clock.today"] = _clock.today
    _orig_now = _clock.now

    def _patched_now(market: str | None = None) -> _dt.datetime:
        override = _REPLAY_NOW.get()
        if override is not None:
            zone = _clock.zone_for_market(market)
            return override.astimezone(zone)
        return _orig_now(market)

    def _patched_today(market: str | None = None) -> _dt.date:
        return _patched_now(market).date()

    _clock.now = _patched_now
    _clock.today = _patched_today

    # 2) llm service
    from llm import service as _svc

    _orig["svc.complete_with_tools"] = _svc.complete_with_tools
    _orig["svc.complete"] = _svc.complete
    _orig_cwt = _svc.complete_with_tools
    _orig_c = _svc.complete

    async def _wrapped_cwt(messages, *, tools, executor, max_tokens=400):
        result, latency_ms, success, error = await _orig_cwt(
            messages, tools=tools, executor=executor, max_tokens=max_tokens
        )
        _record(result, latency_ms, success, error)
        return result, latency_ms, success, error

    async def _wrapped_c(messages, *, max_tokens=300):
        result, latency_ms, success, error = await _orig_c(messages, max_tokens=max_tokens)
        _record(result, latency_ms, success, error)
        return result, latency_ms, success, error

    _svc.complete_with_tools = _wrapped_cwt
    _svc.complete = _wrapped_c

    _installed = True


def _record(result, latency_ms: float, success: bool, error: Optional[str]) -> None:
    records = _LLM_RECORDS.get()
    if records is None:
        return
    records.append(
        LLMCallRecord(
            text=getattr(result, "text", "") or "",
            model=getattr(result, "model", "") or "",
            tokens_in=getattr(result, "tokens_in", 0) or 0,
            tokens_out=getattr(result, "tokens_out", 0) or 0,
            cache_read=getattr(result, "cache_read_tokens", 0) or 0,
            cache_write=getattr(result, "cache_write_tokens", 0) or 0,
            cost_usd=float(getattr(result, "cost_usd", 0.0) or 0.0),
            latency_ms=latency_ms,
            stop_reason=getattr(result, "stop_reason", "") or "",
            tool_rounds=getattr(result, "tool_rounds", 0) or 0,
            success=success,
            error=error or "",
            tool_calls=list(getattr(result, "tool_calls", []) or []),
        )
    )


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    from services import clock as _clock
    from llm import service as _svc

    if "clock.now" in _orig:
        _clock.now = _orig["clock.now"]
    if "clock.today" in _orig:
        _clock.today = _orig["clock.today"]
    if "svc.complete_with_tools" in _orig:
        _svc.complete_with_tools = _orig["svc.complete_with_tools"]
    if "svc.complete" in _orig:
        _svc.complete = _orig["svc.complete"]
    _orig.clear()
    _installed = False
