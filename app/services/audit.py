"""Audit logging service.

Every agent decision, tool call, and cost event must go through here so the
AIActionLog table is the single, complete record of what the agent did.
Never call AsyncSession directly to write an AIActionLog row from anywhere
else - route it through log_action so behavior (including future retries or
notification hooks) stays consistent.
"""
import time
import uuid
from contextlib import contextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_action_log import AIActionLog


async def log_action(
    db: AsyncSession,
    *,
    market_id: uuid.UUID,
    agent_name: str,
    action_type: str,
    conversation_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    tool_name: str | None = None,
    input_json: dict | None = None,
    output_json: dict | None = None,
    model_name: str | None = None,
    provider: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    estimated_cost: float = 0.0,
    latency_ms: int | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> AIActionLog:
    log = AIActionLog(
        market_id=market_id,
        conversation_id=conversation_id,
        order_id=order_id,
        agent_name=agent_name,
        action_type=action_type,
        tool_name=tool_name,
        input_json=input_json or {},
        output_json=output_json or {},
        model_name=model_name,
        provider=provider,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        success=success,
        error_message=error_message,
    )
    db.add(log)
    await db.flush()
    return log


@contextmanager
def timed():
    """Usage: with timed() as t: ...; t.ms holds elapsed milliseconds after the block."""

    class _Timer:
        ms: int = 0

    t = _Timer()
    start = time.perf_counter()
    try:
        yield t
    finally:
        t.ms = int((time.perf_counter() - start) * 1000)
