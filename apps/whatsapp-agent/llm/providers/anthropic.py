"""Real Anthropic provider. Only ever instantiated/used when
settings.live_llm_ready is True (llm_provider == "anthropic" AND
ANTHROPIC_API_KEY is set) - see llm/service.py's _select_provider(). Never
imported or called directly from agent code.
"""
from anthropic import AsyncAnthropic

from llm.providers.base import LLMMessage, LLMProvider, LLMResult


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model or "claude-haiku-4-5-20251001"

    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult:
        system = "\n".join(m.content for m in messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=turns,
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return LLMResult(
            text=text,
            provider=self.name,
            model=self._model,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
