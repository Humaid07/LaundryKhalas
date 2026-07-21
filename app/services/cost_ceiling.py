"""Cost ceiling placeholders (Redis-backed).

For this MVP only the per-run tool-step cap is actually enforced (see
app.agents.whatsapp_operations.graph.execute_tool_loop, gated by
Settings.cost_max_tool_steps_per_run). The per-conversation, per-customer/day,
and global daily ceilings below have their config structure and Redis
counters in place, and every LLM call records against them (see
llm.service.complete), but nothing currently blocks a call for exceeding
them - that enforcement is required future work before live launch (see
docs/checklists/live-whatsapp-readiness.md).
"""
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.redis import get_redis


def _today_key(*parts: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ":".join(["cost", day, *parts])


async def record_cost_event(
    *,
    conversation_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
) -> None:
    redis_client = get_redis()
    total_tokens = tokens_in + tokens_out

    pipe = redis_client.pipeline()
    if conversation_id:
        pipe.incrby(_today_key("conversation", str(conversation_id), "tokens"), total_tokens)
    if customer_id:
        pipe.incrbyfloat(_today_key("customer", str(customer_id), "spend"), estimated_cost)
    pipe.incrbyfloat(_today_key("global", "spend"), estimated_cost)
    await pipe.execute()


async def conversation_tokens_today(conversation_id: uuid.UUID) -> int:
    redis_client = get_redis()
    value = await redis_client.get(_today_key("conversation", str(conversation_id), "tokens"))
    return int(value) if value else 0


async def customer_spend_today(customer_id: uuid.UUID) -> float:
    redis_client = get_redis()
    value = await redis_client.get(_today_key("customer", str(customer_id), "spend"))
    return float(value) if value else 0.0


async def global_spend_today() -> float:
    redis_client = get_redis()
    value = await redis_client.get(_today_key("global", "spend"))
    return float(value) if value else 0.0


async def is_within_conversation_ceiling(conversation_id: uuid.UUID) -> bool:
    settings = get_settings()
    used = await conversation_tokens_today(conversation_id)
    return used < settings.cost_max_tokens_per_conversation_per_day


async def is_within_customer_daily_ceiling(customer_id: uuid.UUID) -> bool:
    settings = get_settings()
    spent = await customer_spend_today(customer_id)
    return spent < settings.cost_max_spend_per_customer_per_day_usd


async def is_within_global_daily_ceiling() -> bool:
    settings = get_settings()
    spent = await global_spend_today()
    return spent < settings.cost_max_global_spend_per_day_usd
