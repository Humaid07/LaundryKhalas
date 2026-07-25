"""The single entry point for every LLM call in this standalone agent. No
agent/tool code may import a provider directly - always go through
llm_service.complete(). This is what guarantees mock-by-default: a real
provider is only ever selected when its env key is actually present.
"""
import time

from llm.providers.base import LLMMessage, LLMProvider, LLMResult, ToolExecutor
from llm.providers.mock import MockProvider
from settings import get_settings

_mock = MockProvider()


def _select_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.live_llm_ready:
        return _mock

    if settings.llm_provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key, settings.llm_model)
    if settings.llm_provider == "openai":
        from llm.providers.openai import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key, settings.llm_model)
    return _mock


async def complete(
    messages: list[LLMMessage], *, max_tokens: int = 300
) -> tuple[LLMResult, float, bool, str | None]:
    """Returns (result, latency_ms, success, error_message)."""
    provider = _select_provider()
    start = time.perf_counter()
    try:
        result = await provider.complete(messages, max_tokens=max_tokens)
        latency_ms = (time.perf_counter() - start) * 1000
        return result, latency_ms, True, None
    except Exception as exc:  # noqa: BLE001 - always fall back safely, never crash the reply path
        latency_ms = (time.perf_counter() - start) * 1000
        fallback = await _mock.complete(messages, max_tokens=max_tokens)
        return fallback, latency_ms, False, str(exc)


async def complete_with_tools(
    messages: list[LLMMessage],
    *,
    tools: list[dict],
    executor: ToolExecutor,
    max_tokens: int = 400,
) -> tuple[LLMResult, float, bool, str | None]:
    """Tool-enabled turn: the selected provider may request grounded backend
    tools (validated + executed by ``executor``) before producing the final
    reply. Same safety contract as ``complete()`` — on ANY failure (including a
    tool loop that doesn't converge) it falls back to the deterministic mock so
    the customer always gets a safe reply, and the reply path never crashes.

    In mock mode the base provider ignores the tools and returns the same
    rule-based reply as ``complete()`` — so nothing changes offline."""
    provider = _select_provider()
    start = time.perf_counter()
    try:
        result = await provider.complete_with_tools(
            messages, tools=tools, executor=executor, max_tokens=max_tokens
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return result, latency_ms, True, None
    except Exception as exc:  # noqa: BLE001 - safe fallback, never crash the reply path
        latency_ms = (time.perf_counter() - start) * 1000
        fallback = await _mock.complete(messages, max_tokens=max_tokens)
        return fallback, latency_ms, False, str(exc)
