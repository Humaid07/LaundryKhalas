"""OpenAI provider - STUB ONLY.

Disabled unless LLM_DEFAULT_PROVIDER=openai AND LLM_ENABLE_OPENAI=true are
both set (see app.core.config.Settings.live_llm_allowed). No OpenAI SDK is
imported or called in this task - that is deliberate.
"""
from app.llm.providers.base import LLMMessage, LLMProvider, LLMResult


class OpenAIProviderStub(LLMProvider):
    name = "openai"

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResult:
        raise NotImplementedError(
            "OpenAIProvider is a stub in this task. Live OpenAI calls are "
            "intentionally disabled. Enable and implement only in a dedicated "
            "future task, behind LLM_ENABLE_OPENAI."
        )
