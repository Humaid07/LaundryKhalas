"""Common types every provider implements.

The abstraction has two entry points, both routed through ``llm/service.py``:

  * ``complete()``            — plain text-in / text-out (unchanged; the mock
                                and legacy path use this).
  * ``complete_with_tools()`` — a tool-use / agentic turn where the model may
                                request one or more grounded backend tools
                                (pricing / catalogue / delivery). The backend
                                validates + executes each tool and feeds the
                                result back until the model produces a final
                                reply. Booking transitions are NEVER a tool —
                                the deterministic FSM owns those.

Only ``AnthropicProvider`` implements a real tool loop; the base default falls
back to ``complete()`` (ignoring the tools) so the mock and OpenAI providers —
and therefore every offline test — behave exactly as before.
"""
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# A tool executor is supplied by the caller (the agent layer). Given a tool
# name + validated-by-the-model input dict, it returns (result_text, is_error).
# The executor is the ONLY thing that touches the deterministic engines, so all
# validation + logging lives on the backend side, never in the model.
ToolExecutor = Callable[[str, dict], Awaitable[tuple[str, bool]]]


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ToolCall:
    """One grounded tool the model requested during a turn, plus the backend's
    result. Persisted (name + is_error) as message metadata so every tool call
    is auditable (CLAUDE.md §11)."""
    name: str
    input: dict
    result: str
    is_error: bool = False


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    # Prompt-cache accounting (Anthropic only; 0 elsewhere). cache_read is
    # billed at ~0.1x, cache_write at ~1.25x — see llm/costs.py.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    stop_reason: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Estimated USD cost of this turn (all API round-trips summed). 0 for mock.
    cost_usd: float = 0.0
    # Anthropic request id (last round-trip) for support/debugging; None for mock.
    request_id: str | None = None
    # Total tool rounds the loop ran (0 for a plain text reply).
    tool_rounds: int = 0


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult: ...

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict],
        executor: ToolExecutor,
        max_tokens: int = 400,
        max_iterations: int = 5,
    ) -> LLMResult:
        """Default: providers without native tool use ignore the tools and
        return a plain completion. Overridden by AnthropicProvider with a real
        agentic loop. Keeping the default here means the mock provider (and thus
        every offline test) is unaffected by the tool wiring."""
        return await self.complete(messages, max_tokens=max_tokens)
