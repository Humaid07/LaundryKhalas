"""The single entry point for every LLM call in this standalone agent. No
agent/tool code may import a provider directly - always go through
llm_service.complete(). This is what guarantees mock-by-default: a real
provider is only ever selected when its env key is actually present.
"""
import asyncio
import time

from llm.providers.base import LLMMessage, LLMProvider, LLMResult, ToolExecutor
from llm.providers.mock import MockProvider
from settings import get_settings

_mock = MockProvider()

# One reusable provider instance per (provider, model, key) — building a new
# AsyncAnthropic client for every WhatsApp message is wasteful. Rebuilt only
# when the resolved config actually changes (e.g. after a settings reload).
_provider_cache: dict[tuple, LLMProvider] = {}

# The classifier runs on its OWN model (ANTHROPIC_CLASSIFIER_MODEL), independent
# of the customer-facing agent — so it gets its own cached provider instance,
# keyed by classifier config, and is never mixed with the main-agent cache above.
_classifier_provider_cache: dict[tuple, LLMProvider] = {}


def _select_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.live_llm_ready:
        return _mock

    provider = settings.ai_provider_effective
    if provider == "anthropic":
        model = settings.anthropic_model_effective
        # Cache key includes every field that changes provider behaviour so a
        # settings reload (e.g. flipping the cache off, or changing the model for
        # rollback) rebuilds the client instead of serving a stale one.
        cache_key = (
            "anthropic", model, settings.anthropic_api_key,
            settings.anthropic_prompt_cache_enabled,
            settings.anthropic_system_cache_ttl,
            settings.anthropic_history_cache_ttl,
            settings.anthropic_temperature_effective,
            settings.anthropic_extended_thinking,
            settings.anthropic_whatsapp_effort,
            settings.anthropic_whatsapp_thinking_mode,
            settings.anthropic_whatsapp_thinking_display,
        )
        cached = _provider_cache.get(cache_key)
        if cached is None:
            from llm.providers.anthropic import AnthropicProvider

            cached = AnthropicProvider(
                settings.anthropic_api_key,
                model,
                timeout_seconds=settings.anthropic_timeout_seconds,
                max_retries=settings.anthropic_max_retries,
                max_tool_rounds=settings.anthropic_max_tool_rounds,
                max_tokens=settings.anthropic_max_tokens,
                temperature=settings.anthropic_temperature_effective,
                prompt_cache_enabled=settings.anthropic_prompt_cache_enabled,
                system_cache_ttl=settings.anthropic_system_cache_ttl,
                history_cache_ttl=settings.anthropic_history_cache_ttl,
                extended_thinking=settings.anthropic_extended_thinking,
                effort=settings.anthropic_whatsapp_effort,
                thinking_mode=settings.anthropic_whatsapp_thinking_mode,
                thinking_display=settings.anthropic_whatsapp_thinking_display,
            )
            _provider_cache.clear()  # only the current config needs caching
            _provider_cache[cache_key] = cached
        return cached
    if provider == "openai":
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


def _select_classifier_provider() -> LLMProvider | None:
    """Build/cache the Anthropic provider for the CLASSIFIER model. Returns None
    when the classifier cannot go live (not Anthropic, disabled, or no key) — the
    caller then uses the deterministic rule engine instead. The classifier is a
    single forced-tool call: NO extended reasoning by default (thinking off, low
    effort) so it stays fast and cheap, and its own bounded retry (1) keeps it
    inside the tight timeout budget."""
    settings = get_settings()
    if settings.ai_provider_effective != "anthropic":
        return None
    if not settings.anthropic_enabled or not settings.anthropic_api_key:
        return None
    model = settings.classifier_model_effective
    timeout_s = max(1, round(settings.whatsapp_classifier_timeout_ms / 1000))
    cache_key = (
        "classifier", model, settings.anthropic_api_key,
        settings.whatsapp_classifier_prompt_cache_enabled,
        settings.anthropic_system_cache_ttl,
        settings.whatsapp_classifier_max_tokens,
        settings.anthropic_classifier_effort,
        settings.anthropic_classifier_thinking_mode,
        timeout_s,
    )
    cached = _classifier_provider_cache.get(cache_key)
    if cached is None:
        from llm.providers.anthropic import AnthropicProvider

        cached = AnthropicProvider(
            settings.anthropic_api_key,
            model,
            timeout_seconds=timeout_s,
            max_retries=1,  # one safe retry only; the wait_for budget caps total time
            max_tokens=settings.whatsapp_classifier_max_tokens,
            prompt_cache_enabled=settings.whatsapp_classifier_prompt_cache_enabled,
            system_cache_ttl=settings.anthropic_system_cache_ttl,
            history_cache_ttl=settings.anthropic_history_cache_ttl,
            effort=settings.anthropic_classifier_effort,
            thinking_mode=settings.anthropic_classifier_thinking_mode,
            thinking_display="omitted",
        )
        _classifier_provider_cache.clear()
        _classifier_provider_cache[cache_key] = cached
    return cached


async def classify_structured(
    system_prompt: str,
    user_payload: str,
    *,
    tool: dict,
    tool_name: str,
    max_tokens: int,
    timeout_seconds: float,
) -> tuple[dict | None, LLMResult | None, float, bool, str | None]:
    """One forced-tool classification call. Returns
    (parsed_input, usage_result, latency_ms, success, error). On any failure or
    timeout returns (None, None, latency, False, error) so the caller falls back
    to a safe UNKNOWN classification — it NEVER raises into the reply path."""
    provider = _select_classifier_provider()
    if provider is None:
        return None, None, 0.0, False, "classifier provider unavailable"
    messages = [
        LLMMessage(role="system", content=system_prompt, cache="1h"),
        LLMMessage(role="user", content=user_payload),
    ]
    start = time.perf_counter()
    try:
        result, parsed = await asyncio.wait_for(
            provider.complete_structured(
                messages, tool=tool, tool_name=tool_name, max_tokens=max_tokens
            ),
            timeout=timeout_seconds,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return parsed, result, latency_ms, True, None
    except Exception as exc:  # noqa: BLE001 - timeout/transport/etc → safe UNKNOWN
        latency_ms = (time.perf_counter() - start) * 1000
        return None, None, latency_ms, False, str(exc)
