"""LLM provider interface.

No code outside app/llm may call a provider's SDK directly - always go
through llm.service.complete(), which is responsible for provider
selection, cost estimation, and audit logging.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict]
    model_name: str
    provider: str
    tokens_in: int
    tokens_out: int
    estimated_cost: float


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResult:
        ...
