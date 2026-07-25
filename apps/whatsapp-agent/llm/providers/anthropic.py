"""Real Anthropic (Claude) provider. Only ever instantiated/used when
settings.live_llm_ready is True (provider == "anthropic", ANTHROPIC_ENABLED,
AND ANTHROPIC_API_KEY present) — see llm/service.py's _select_provider(), which
also CACHES a single instance so we don't build a new client per WhatsApp
message. Never imported or called directly from agent code.

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
  * capture real token usage (incl. cache read/write), request id + est. cost;
  * use APPLICATION-controlled retries (bounded exponential backoff + jitter);
    the SDK's own retries are turned OFF (max_retries=0) so the two don't stack.
"""
from __future__ import annotations

import asyncio
import random

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)

from llm.costs import estimate_cost_usd
from llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResult,
    ToolCall,
    ToolExecutor,
)
from settings import DEFAULT_ANTHROPIC_MODEL

# Model families that REJECT sampling params (temperature/top_p/top_k) — sending
# temperature to these returns a 400. Current default models are all here, so we
# omit temperature unless a legacy model that supports it is configured.
_NO_SAMPLING_PARAMS = (
    "opus-4-6", "opus-4-7", "opus-4-8", "sonnet-5", "sonnet-4-6", "fable-5", "mythos-5",
)

# Backoff bounds for application-controlled retries.
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_CAP_SECONDS = 8.0


def _is_retryable(exc: Exception) -> bool:
    """Transient failures worth retrying; auth/validation (4xx except 429) are not."""
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500
    return False


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: AsyncAnthropic | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        max_tool_rounds: int = 5,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> None:
        # `client` is injectable so the tool loop / retry logic can be
        # unit-tested offline against a scripted fake — no network, no key.
        # SDK retries are OFF (max_retries=0) — the application controls retries
        # below so app + SDK backoff never stack.
        self._client = client or AsyncAnthropic(
            api_key=api_key, max_retries=0, timeout=float(timeout_seconds)
        )
        self._model = model or DEFAULT_ANTHROPIC_MODEL
        self._max_retries = max_retries
        self._max_tool_rounds = max_tool_rounds
        self._max_tokens = max_tokens
        self._temperature = temperature

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
        if not system:
            return None
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    @staticmethod
    def _cacheable_tools(tools: list[dict]) -> list[dict]:
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

    def _supports_temperature(self) -> bool:
        return not any(tag in self._model for tag in _NO_SAMPLING_PARAMS)

    async def _create(self, **kwargs):
        """One Messages API call with application-controlled retry (bounded
        exponential backoff + jitter). Non-retryable errors (auth/validation)
        propagate immediately; the service layer falls back to the safe mock."""
        attempt = 0
        while True:
            try:
                return await self._client.messages.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 - classified below
                if not _is_retryable(exc) or attempt >= self._max_retries:
                    raise
                delay = min(_BACKOFF_BASE_SECONDS * (2 ** attempt), _BACKOFF_CAP_SECONDS)
                delay += random.uniform(0, 0.5)  # jitter to avoid thundering herd
                attempt += 1
                await asyncio.sleep(delay)

    def _tally(self, usage, running: dict) -> None:
        running["tokens_in"] += getattr(usage, "input_tokens", 0) or 0
        running["tokens_out"] += getattr(usage, "output_tokens", 0) or 0
        running["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        running["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def _result(self, text, running, *, stop_reason=None, tool_calls=None,
                request_id=None, tool_rounds=0) -> LLMResult:
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
            request_id=request_id,
            tool_rounds=tool_rounds,
            cost_usd=estimate_cost_usd(
                self._model,
                tokens_in=running["tokens_in"],
                tokens_out=running["tokens_out"],
                cache_read_tokens=running["cache_read"],
                cache_write_tokens=running["cache_write"],
            ),
        )

    def _base_kwargs(self, max_tokens: int | None) -> dict:
        kwargs: dict = {"model": self._model, "max_tokens": max_tokens or self._max_tokens}
        if self._supports_temperature():
            kwargs["temperature"] = self._temperature
        return kwargs

    # ---- entry points ------------------------------------------------------
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int | None = None
    ) -> LLMResult:
        system, turns = self._split(messages)
        running = {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0}
        kwargs = self._base_kwargs(max_tokens)
        kwargs["messages"] = turns
        system_blocks = self._system_blocks(system)
        if system_blocks:
            kwargs["system"] = system_blocks
        response = await self._create(**kwargs)
        self._tally(response.usage, running)
        return self._result(
            self._text_of(response.content), running,
            stop_reason=getattr(response, "stop_reason", None),
            request_id=getattr(response, "_request_id", None),
        )

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict],
        executor: ToolExecutor,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
    ) -> LLMResult:
        """Manual agentic loop. Claude requests grounded tools; the executor
        (backend-side, validated) runs them; results feed back until Claude
        returns a final reply. Tool inputs are always parsed as structured
        dicts by the SDK — the deterministic engines do the real work."""
        rounds = max_iterations or self._max_tool_rounds
        system, turns = self._split(messages)
        system_blocks = self._system_blocks(system)
        cached_tools = self._cacheable_tools(tools)
        running = {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0}
        convo: list[dict] = list(turns)
        tool_calls: list[ToolCall] = []
        request_id = None

        for round_no in range(1, rounds + 1):
            kwargs = self._base_kwargs(max_tokens)
            kwargs["messages"] = convo
            kwargs["tools"] = cached_tools
            if system_blocks:
                kwargs["system"] = system_blocks
            response = await self._create(**kwargs)
            self._tally(response.usage, running)
            request_id = getattr(response, "_request_id", None) or request_id
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
                convo.append({"role": "assistant", "content": response.content})
                continue

            # end_turn / stop_sequence / refusal / max_tokens → we're done.
            return self._result(
                self._text_of(response.content), running,
                stop_reason=stop, tool_calls=tool_calls,
                request_id=request_id, tool_rounds=round_no,
            )

        # Reached the tool-round limit without a final reply. Raise so the
        # service layer falls back to a safe deterministic reply rather than
        # sending a half-finished / empty message. Workflow state is untouched.
        raise RuntimeError(
            f"Anthropic tool loop did not converge in {rounds} rounds"
        )
