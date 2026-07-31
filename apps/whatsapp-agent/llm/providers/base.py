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
    # Prompt-cache hint for the Anthropic provider (ignored by mock/openai):
    #   None  → no breakpoint here (dynamic content — must stay AFTER the last one)
    #   "1h"  → stable prefix, 1-hour ephemeral cache (system prompt)
    #   "5m"  → reusable conversation prefix, 5-minute ephemeral cache (history)
    # Any byte change before a breakpoint invalidates it, so only mark blocks that
    # are byte-identical across turns/customers.
    cache: str | None = None


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
    # billed at ~0.1x, cache_write at ~1.25x (5m) / ~2x (1h) — see llm/costs.py.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # Split of cache-write tokens by TTL when the SDK reports it (Anthropic
    # usage.cache_creation.ephemeral_{5m,1h}_input_tokens); 0 when unavailable.
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    stop_reason: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Estimated USD cost of this turn (all API round-trips summed). 0 for mock.
    cost_usd: float = 0.0
    # Anthropic request id (last round-trip) for support/debugging; None for mock.
    request_id: str | None = None
    # Total tool rounds the loop ran (0 for a plain text reply).
    tool_rounds: int = 0

    @property
    def cache_hit(self) -> bool:
        """True when any part of the prompt was served from cache this turn."""
        return self.cache_read_tokens > 0

    @property
    def total_input_tokens(self) -> int:
        """Full prompt size: uncached input + cache reads + cache writes.
        ``tokens_in`` alone is only the uncached remainder (Anthropic reports the
        cached buckets separately) — see llm/costs.py / shared prompt-caching."""
        return self.tokens_in + self.cache_read_tokens + self.cache_write_tokens


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
