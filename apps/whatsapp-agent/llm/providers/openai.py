"""Real OpenAI provider, optional. Only used when llm_provider == "openai"
AND OPENAI_API_KEY is set. Uses raw httpx rather than the openai SDK to
avoid an extra hard dependency for a secondary/optional provider.
"""
import httpx

from llm.providers.base import LLMMessage, LLMProvider, LLMResult

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model or "gpt-4o-mini"

    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(_CHAT_COMPLETIONS_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            provider=self.name,
            model=self._model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )
