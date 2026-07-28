"""LLM gateway.

The single entry point for every LLM call in the codebase. No agent, tool,
or route may import a provider or SDK directly - always go through
llm_service.complete(). This is what guarantees every call is logged with
cost/tokens/latency and that live providers stay off unless explicitly
enabled.
"""
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.llm.providers.anthropic_stub import AnthropicProviderStub
from app.llm.providers.base import LLMMessage, LLMProvider, LLMResult
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai_stub import OpenAIProviderStub
from app.services import cost_ceiling
from app.services.audit import log_action

_PROVIDERS: dict[str, LLMProvider] = {
    "mock": MockProvider(),
    "anthropic": AnthropicProviderStub(),
    "openai": OpenAIProviderStub(),
}


def _select_provider() -> LLMProvider:
    settings = get_settings()
    if settings.live_llm_allowed:
        return _PROVIDERS[settings.llm_default_provider]
    # Safe default: mock, regardless of what LLM_DEFAULT_PROVIDER says, unless
    # that provider has been explicitly enabled via its own feature flag.
    return _PROVIDERS["mock"]


async def complete(
    db: AsyncSession,
    *,
    market_id: uuid.UUID,
    agent_name: str,
    messages: list[LLMMessage],
    tools: list[dict] | None = None,
    tier: str = "routine",
    conversation_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
) -> LLMResult:
    settings = get_settings()
    provider = _select_provider()

    success = True
    error_message: str | None = None
    result: LLMResult | None = None

    start = time.perf_counter()
    try:
        result = await provider.complete(
            messages, tools=tools, max_tokens=settings.llm_max_tokens_per_call
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad, logged then re-raised
        success = False
        error_message = str(exc)
        raise
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        await log_action(
            db,
            market_id=market_id,
            conversation_id=conversation_id,
            order_id=order_id,
            agent_name=agent_name,
            action_type="llm_complete",
            input_json={"tier": tier, "message_count": len(messages)},
            output_json={"text": result.text} if result else {},
            model_name=result.model_name if result else None,
            provider=provider.name,
            tokens_in=result.tokens_in if result else 0,
            tokens_out=result.tokens_out if result else 0,
            estimated_cost=result.estimated_cost if result else 0.0,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
        )
        if result is not None:
            try:
                await cost_ceiling.record_cost_event(
                    conversation_id=conversation_id,
                    customer_id=None,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    estimated_cost=result.estimated_cost,
                )
            except Exception:  # noqa: BLE001 - cost tracking must never break the LLM call
                pass

    assert result is not None
    return result
