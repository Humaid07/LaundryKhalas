"""Common types every provider implements."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult: ...
