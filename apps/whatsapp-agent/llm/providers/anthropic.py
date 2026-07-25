"""Real Anthropic (Claude) provider. Only ever instantiated/used when
settings.live_llm_ready is True (llm_provider == "anthropic" AND
ANTHROPIC_API_KEY is set) — see llm/service.py's _select_provider(). Never
imported or called directly from agent code.

Two entry points:
  * complete()            — plain text completion (legacy path).
  * complete_with_tools() — an agentic tool loop. Claude may request grounded
    backend tools (pricing / catalogue / delivery); the caller's executor
    validates + runs each against the deterministic engines and feeds results
    back until Claude produces a final customer reply. Claude NEVER decides a
    booking transition — that stays in services/booking_flow.py.

Both paths:
  * cache the (large, stable) system prompt and the tool set as a prompt-cache
    prefix so repeat turns are ~90% cheaper on the cached portion;
  * capture real token usage (incl. cache read/write) and an estimated cost;
  * rely on the SDK's built-in retry/backoff (max_retries) for 429/5xx/network.
"""
from __future__ import annotations

from anthropic import AsyncAnthropic

from llm.costs import estimate_cost_usd
from llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResult,
    ToolCall,
    ToolExecutor,
)

# Per the Claude API reference, default to the most capable current model. The
# operator can override to a cheaper tier for this high-volume real-time path
# via LLM_MODEL (e.g. claude-haiku-4-5) — that is a deliberate cost decision,
# left to the operator, not hardcoded down here.
DEFAULT_MODEL = "claude-opus-4-8"

# Bound the agentic loop so a misbehaving turn can never spin forever. A booking
# Q&A needs at most a couple of grounded lookups; exceeding this raises so the
# service layer falls back to the safe deterministic mock reply.
_MAX_ITERATIONS = 5


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, *, client: AsyncAnthropic | None = None) -> None:
        # `client` is injectable so the tool loop can be unit-tested offline
        # against a scripted fake — no network, no key.
        self._client = client or AsyncAnthropic(api_key=api_key, max_retries=3)
        self._model = model or DEFAULT_MODEL

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _split(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        system = "\n".join(m.content for m in messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        return system, turns

    @staticmethod
    def _system_blocks(system: str) -> list[dict] | None:
        """Cache the system prompt as a stable prefix (big, unchanging → cheap
        on every repeat turn). Returns None when there is no system text."""
        if not system:
            return None
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    @staticmethod
    def _cacheable_tools(tools: list[dict]) -> list[dict]:
        """Copy the tool set and mark the LAST tool with cache_control so the
        whole (stable, deterministic-order) tools block is cached alongside the
        system prompt."""
        if not tools:
            return []
        out = [dict(t) for t in tools]
        out[-1] = {**out[-1], "cache_control": {"type": "ephemeral"}}
        return out

    @staticmethod
    def _text_of(content) -> str:
        return "".join(
            b.text for b in content if getattr(b, "type", "") == "text"
        ).strip()

    def _tally(self, usage, running: dict) -> None:
        running["tokens_in"] += getattr(usage, "input_tokens", 0) or 0
        running["tokens_out"] += getattr(usage, "output_tokens", 0) or 0
        running["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        running["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def _result(self, text: str, running: dict, *, stop_reason=None, tool_calls=None) -> LLMResult:
        return LLMResult(
            text=text,
            provider=self.name,
            model=self._model,
            tokens_in=running["tokens_in"],
            tokens_out=running["tokens_out"],
            cache_read_tokens=running["cache_read"],
            cache_write_tokens=running["cache_write"],
            stop_reason=stop_reason,
            tool_calls=tool_calls or [],
            cost_usd=estimate_cost_usd(
                self._model,
                tokens_in=running["tokens_in"],
                tokens_out=running["tokens_out"],
                cache_read_tokens=running["cache_read"],
                cache_write_tokens=running["cache_write"],
            ),
        )

    # ---- entry points ------------------------------------------------------
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 300
    ) -> LLMResult:
        system, turns = self._split(messages)
        running = {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0}
        kwargs: dict = {"model": self._model, "max_tokens": max_tokens, "messages": turns}
        system_blocks = self._system_blocks(system)
        if system_blocks:
            kwargs["system"] = system_blocks
        response = await self._client.messages.create(**kwargs)
        self._tally(response.usage, running)
        return self._result(
            self._text_of(response.content), running,
            stop_reason=getattr(response, "stop_reason", None),
        )

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict],
        executor: ToolExecutor,
        max_tokens: int = 400,
        max_iterations: int = _MAX_ITERATIONS,
    ) -> LLMResult:
        """Manual agentic loop. Claude requests grounded tools; the executor
        (backend-side, validated) runs them; results feed back until Claude
        returns a final reply. Tool inputs are always parsed as structured
        dicts by the SDK — the deterministic engines do the real work."""
        system, turns = self._split(messages)
        system_blocks = self._system_blocks(system)
        cached_tools = self._cacheable_tools(tools)
        running = {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0}
        convo: list[dict] = list(turns)
        tool_calls: list[ToolCall] = []

        for _ in range(max_iterations):
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": convo,
                "tools": cached_tools,
            }
            if system_blocks:
                kwargs["system"] = system_blocks
            response = await self._client.messages.create(**kwargs)
            self._tally(response.usage, running)
            stop = getattr(response, "stop_reason", None)

            if stop == "tool_use":
                convo.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if getattr(block, "type", "") != "tool_use":
                        continue
                    tool_input = dict(block.input) if isinstance(block.input, dict) else {}
                    result_text, is_error = await executor(block.name, tool_input)
                    tool_calls.append(
                        ToolCall(name=block.name, input=tool_input,
                                 result=result_text, is_error=is_error)
                    )
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": is_error,
                    })
                convo.append({"role": "user", "content": results})
                continue

            if stop == "pause_turn":
                # Server-side tool paused mid-turn — resend to continue.
                convo.append({"role": "assistant", "content": response.content})
                continue

            # end_turn / stop_sequence / refusal / max_tokens → we're done.
            return self._result(
                self._text_of(response.content), running,
                stop_reason=stop, tool_calls=tool_calls,
            )

        # Exhausted the loop without a final reply. Raise so the service layer
        # falls back to the safe deterministic mock reply rather than sending a
        # half-finished or empty message.
        raise RuntimeError(
            f"Anthropic tool loop did not converge in {max_iterations} iterations"
        )
