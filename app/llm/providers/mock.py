"""Deterministic mock LLM provider.

Returns the content of the last message verbatim as its completion. Callers
(agent tools) are responsible for building the actual reply/question text
from DB/config data before calling llm_service.complete() - the mock
provider's job is only to exercise the gateway plumbing (token/cost
estimation, audit logging) deterministically, never to invent content.
"""
from app.llm.providers.base import LLMMessage, LLMProvider, LLMResult


def _estimate_tokens(text: str) -> int:
    # Rough deterministic estimate: ~4 chars per token, minimum 1.
    return max(1, len(text) // 4)


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResult:
        last = messages[-1] if messages else LLMMessage(role="user", content="")
        text = last.content

        tokens_in = sum(_estimate_tokens(m.content) for m in messages)
        tokens_out = _estimate_tokens(text)

        return LLMResult(
            text=text,
            tool_calls=[],
            model_name="mock-echo-1",
            provider=self.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost=0.0,
        )
