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
# temperature to these returns a 400. This is ALSO exactly the family that takes
# adaptive thinking (thinking={"type":"adaptive"}) and output_config.effort, so we
# reuse it as the single gate: for these models we send effort + adaptive thinking
# instead of temperature; for older models (e.g. Haiku 4.5) we send temperature and
# NEVER send effort/thinking (both would 400 there).
_NO_SAMPLING_PARAMS = (
    "opus-4-6", "opus-4-7", "opus-4-8", "sonnet-5", "sonnet-4-6", "fable-5", "mythos-5",
)

# Reasoning-effort values accepted by output_config.effort on the adaptive family.
_VALID_EFFORT = frozenset({"low", "medium", "high", "xhigh", "max"})

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
        prompt_cache_enabled: bool = True,
        system_cache_ttl: str = "1h",
        history_cache_ttl: str = "5m",
        extended_thinking: bool = False,
        effort: str | None = "high",
        thinking_mode: str = "adaptive",
        thinking_display: str = "omitted",
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
        # Mixed prompt-cache strategy (spec 2026-07-31): stable system+tools on the
        # longer TTL, reusable conversation history on the shorter one. Disable to
        # roll back to an uncached prompt.
        self._prompt_cache_enabled = prompt_cache_enabled
        self._system_cache_ttl = system_cache_ttl
        self._history_cache_ttl = history_cache_ttl
        # Extended thinking stays OFF for normal WhatsApp turns (spec) — we simply
        # never send the `thinking` param. Kept as an explicit flag for visibility.
        self._extended_thinking = extended_thinking
        # Sonnet 5 (adaptive-thinking family) config. `effort` drives depth/spend via
        # output_config.effort; adaptive thinking is the only on-mode (no token budget).
        # Both are sent ONLY for the adaptive family — never to Haiku, where they 400.
        self._effort = (effort or "").strip().lower() or None
        self._thinking_mode = (thinking_mode or "adaptive").strip().lower()
        self._thinking_display = (thinking_display or "omitted").strip().lower()

    # ---- prompt-cache helpers ----------------------------------------------
    def _cc(self, ttl: str | None) -> dict | None:
        """Build a cache_control block for the requested TTL, or None when caching
        is disabled / no TTL. ``"5m"`` is the ephemeral default; ``"1h"`` needs the
        explicit ttl field (and the extended-cache beta header, see _extra_headers)."""
        if not (self._prompt_cache_enabled and ttl):
            return None
        cc: dict = {"type": "ephemeral"}
        if ttl == "1h":
            cc["ttl"] = "1h"
        return cc

    def _uses_1h(self, system_messages: list[LLMMessage], tools: list[dict]) -> bool:
        if not self._prompt_cache_enabled:
            return False
        if tools and self._system_cache_ttl == "1h":
            return True
        any_flag = any(m.cache for m in system_messages if (m.content or "").strip())
        for i, m in enumerate(m for m in system_messages if (m.content or "").strip()):
            ttl = m.cache or (self._system_cache_ttl if not any_flag else None)
            if ttl == "1h":
                return True
        return False

    def _extra_headers(self, system_messages, tools) -> dict | None:
        """The 1-hour ephemeral cache TTL is a beta; send its header whenever a 1h
        breakpoint is actually in play. Harmless when the account already has it GA."""
        if self._uses_1h(system_messages, tools):
            return {"anthropic-beta": "extended-cache-ttl-2025-04-11"}
        return None

    # ---- message assembly --------------------------------------------------
    @staticmethod
    def _split(messages: list[LLMMessage]) -> tuple[list[LLMMessage], list[LLMMessage]]:
        system = [m for m in messages if m.role == "system"]
        turns = [m for m in messages if m.role != "system"]
        return system, turns

    def _turn_dict(self, m: LLMMessage) -> dict:
        """One conversation turn. A ``cache`` flag makes the content a single text
        block carrying cache_control (the 5-minute conversation-prefix breakpoint);
        otherwise it stays a plain string so the wire prompt is minimal."""
        cc = self._cc(m.cache)
        if cc:
            return {"role": m.role,
                    "content": [{"type": "text", "text": m.content, "cache_control": cc}]}
        return {"role": m.role, "content": m.content}

    def _system_blocks(self, system_messages: list[LLMMessage]) -> list[dict] | None:
        """Render system content as text blocks, placing the cache breakpoint(s).
        Each system message may set its own ``cache`` TTL; if NONE do (legacy
        callers), the last block auto-gets the stable system TTL so the big prompt
        still caches. Dynamic content must NOT be a system message — callers put it
        in the message stream AFTER the last breakpoint instead."""
        texts = [m for m in system_messages if (m.content or "").strip()]
        if not texts:
            return None
        any_flag = any(m.cache for m in texts)
        blocks: list[dict] = []
        for i, m in enumerate(texts):
            ttl = m.cache
            if ttl is None and not any_flag and i == len(texts) - 1:
                ttl = self._system_cache_ttl  # backward-compatible auto-placement
            block: dict = {"type": "text", "text": m.content}
            cc = self._cc(ttl)
            if cc:
                block["cache_control"] = cc
            blocks.append(block)
        return blocks

    def _cacheable_tools(self, tools: list[dict]) -> list[dict]:
        """Cache the whole tool set as part of the stable prefix (tools render
        before system, so the 1h breakpoint on the last tool caches all of them)."""
        if not tools:
            return []
        out = [dict(t) for t in tools]
        cc = self._cc(self._system_cache_ttl)
        if cc:
            out[-1] = {**out[-1], "cache_control": cc}
        return out

    @staticmethod
    def _text_of(content) -> str:
        return "".join(
            b.text for b in content if getattr(b, "type", "") == "text"
        ).strip()

    def _supports_temperature(self) -> bool:
        return not any(tag in self._model for tag in _NO_SAMPLING_PARAMS)

    def _is_adaptive_family(self) -> bool:
        """True for models that take adaptive thinking + output_config.effort and
        reject sampling params (Sonnet 5 / Opus 4.6+ / Fable 5). The exact inverse
        of _supports_temperature — one gate, no drift."""
        return not self._supports_temperature()

    def _effort_for_result(self) -> str | None:
        """The effort value actually sent this turn (None when not applicable)."""
        if self._is_adaptive_family() and self._effort in _VALID_EFFORT:
            return self._effort
        return None

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
        # Per-TTL cache-write split (present since the extended-cache beta). Tolerate
        # dict or object shape, and its total absence, without ever crashing a turn.
        creation = getattr(usage, "cache_creation", None)
        if creation is not None:
            def _field(name: str) -> int:
                if isinstance(creation, dict):
                    return creation.get(name, 0) or 0
                return getattr(creation, name, 0) or 0
            running["cache_write_5m"] += _field("ephemeral_5m_input_tokens")
            running["cache_write_1h"] += _field("ephemeral_1h_input_tokens")

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
            cache_write_5m_tokens=running["cache_write_5m"],
            cache_write_1h_tokens=running["cache_write_1h"],
            stop_reason=stop_reason,
            tool_calls=tool_calls or [],
            request_id=request_id,
            tool_rounds=tool_rounds,
            effort=self._effort_for_result(),
            cost_usd=estimate_cost_usd(
                self._model,
                tokens_in=running["tokens_in"],
                tokens_out=running["tokens_out"],
                cache_read_tokens=running["cache_read"],
                cache_write_tokens=running["cache_write"],
            ),
        )

    @staticmethod
    def _new_running() -> dict:
        return {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0,
                "cache_write_5m": 0, "cache_write_1h": 0}

    def _base_kwargs(self, max_tokens: int | None) -> dict:
        kwargs: dict = {"model": self._model, "max_tokens": max_tokens or self._max_tokens}
        if self._supports_temperature():
            # Legacy family (e.g. Haiku 4.5): exactly ONE sampling parameter
            # (temperature); never combined with top_p/top_k (spec). No effort /
            # thinking params — they 400 on these models.
            kwargs["temperature"] = self._temperature
            return kwargs
        # Adaptive family (Sonnet 5 / Opus 4.6+ / Fable 5): NO sampling params at all
        # (temperature/top_p/top_k all 400). Configure reasoning via output_config.effort
        # (GA, no beta header) and adaptive thinking (the only on-mode; no token budget).
        # display defaults to "omitted" so internal reasoning is never surfaced to the
        # customer. All three are omitted entirely for the legacy branch above.
        effort = self._effort_for_result()
        if effort:
            kwargs["output_config"] = {"effort": effort}
        if self._thinking_mode == "adaptive":
            thinking: dict = {"type": "adaptive"}
            if self._thinking_display:
                thinking["display"] = self._thinking_display
            kwargs["thinking"] = thinking
        return kwargs

    # ---- entry points ------------------------------------------------------
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int | None = None
    ) -> LLMResult:
        system, turns = self._split(messages)
        running = self._new_running()
        kwargs = self._base_kwargs(max_tokens)
        kwargs["messages"] = [self._turn_dict(m) for m in turns]
        system_blocks = self._system_blocks(system)
        if system_blocks:
            kwargs["system"] = system_blocks
        headers = self._extra_headers(system, [])
        if headers:
            kwargs["extra_headers"] = headers
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
        headers = self._extra_headers(system, tools)
        running = self._new_running()
        convo: list[dict] = [self._turn_dict(m) for m in turns]
        tool_calls: list[ToolCall] = []
        request_id = None

        for round_no in range(1, rounds + 1):
            kwargs = self._base_kwargs(max_tokens)
            kwargs["messages"] = convo
            kwargs["tools"] = cached_tools
            if system_blocks:
                kwargs["system"] = system_blocks
            if headers:
                kwargs["extra_headers"] = headers
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

            if stop == "refusal":
                # A safety refusal is NOT a valid customer reply and must never be
                # sent as one, nor treated as a completed booking (spec). Raise so
                # the service layer falls back to the safe deterministic mock; the
                # booking FSM state is left untouched for the human queue.
                raise RuntimeError("Anthropic returned stop_reason=refusal")

            # end_turn / stop_sequence / max_tokens → we're done.
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

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        *,
        tool: dict,
        tool_name: str,
        max_tokens: int | None = None,
    ) -> tuple[LLMResult, dict]:
        """Single FORCED-tool call for structured output (the classifier path).

        Unlike ``complete_with_tools`` there is NO agentic loop and NO executor:
        the model is forced (via ``tool_choice``) to return exactly one call to
        ``tool_name`` whose validated input dict IS the structured result, so we
        never regex JSON out of prose. Returns (usage_result, parsed_input).

        The stable system prompt + the tool schema are cached as the reusable
        prefix (same machinery as the other paths); only the per-turn user
        payload is uncached. Raises on refusal / missing tool block so the caller
        can fall back to a safe UNKNOWN classification.
        """
        system, turns = self._split(messages)
        system_blocks = self._system_blocks(system)
        cached_tools = self._cacheable_tools([tool])
        headers = self._extra_headers(system, [tool])
        running = self._new_running()

        kwargs = self._base_kwargs(max_tokens)
        kwargs["messages"] = [self._turn_dict(m) for m in turns]
        kwargs["tools"] = cached_tools
        # Force exactly this one tool; no parallel calls, no free-text answer.
        kwargs["tool_choice"] = {
            "type": "tool",
            "name": tool_name,
            "disable_parallel_tool_use": True,
        }
        if system_blocks:
            kwargs["system"] = system_blocks
        if headers:
            kwargs["extra_headers"] = headers

        response = await self._create(**kwargs)
        self._tally(response.usage, running)
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            raise RuntimeError("classifier structured call refused")

        parsed: dict = {}
        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == tool_name:
                parsed = dict(block.input) if isinstance(block.input, dict) else {}
                break
        if not parsed:
            raise RuntimeError("classifier structured call returned no tool_use block")

        result = self._result(
            "", running,
            stop_reason=stop,
            tool_calls=[ToolCall(name=tool_name, input=parsed, result="", is_error=False)],
            request_id=getattr(response, "_request_id", None),
            tool_rounds=1,
        )
        return result, parsed
