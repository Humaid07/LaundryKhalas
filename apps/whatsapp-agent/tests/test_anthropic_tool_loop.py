"""AnthropicProvider tool loop + cost estimation + service-layer safety.

Runs fully OFFLINE against a scripted fake Anthropic client (no key, no
network) — it exercises the agentic loop wiring, not the real API.
"""
import pytest

from agents.whatsapp_agent.llm_tools import TOOL_SCHEMAS, execute_tool
from llm import costs, service as llm_service
from llm.providers.anthropic import DEFAULT_MODEL, AnthropicProvider
from llm.providers.base import LLMMessage, LLMProvider, LLMResult


# --- Scripted fake Anthropic client ----------------------------------------
class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    def __init__(self, i=0, o=0, cr=0, cw=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw


class _Resp:
    def __init__(self, content, stop_reason, usage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeMessages:
    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._script.pop(0)


class _FakeClient:
    def __init__(self, script):
        self.messages = _FakeMessages(script)


def _text(t):
    return _Block(type="text", text=t)


def _tool_use(name, tool_input, id="t1"):
    return _Block(type="tool_use", name=name, input=tool_input, id=id)


# --- Tests -----------------------------------------------------------------
async def test_tool_loop_calls_backend_then_produces_final_reply():
    script = [
        _Resp([_tool_use("lookup_item_price", {"query": "shirt"})], "tool_use", _Usage(120, 30, cw=800)),
        _Resp([_text("Shirts are AED 9 each (excl. VAT). Want to book a pickup?")],
              "end_turn", _Usage(40, 25, cr=800)),
    ]
    client = _FakeClient(script)
    provider = AnthropicProvider("unused-key", DEFAULT_MODEL, client=client)

    result = await provider.complete_with_tools(
        [LLMMessage(role="system", content="SYS"),
         LLMMessage(role="user", content="how much for a shirt?")],
        tools=TOOL_SCHEMAS, executor=execute_tool,
    )

    assert "AED 9" in result.text
    assert result.provider == "anthropic"
    assert [tc.name for tc in result.tool_calls] == ["lookup_item_price"]
    # usage summed across both round-trips
    assert result.tokens_in == 160
    assert result.tokens_out == 55
    assert result.cache_write_tokens == 800
    assert result.cache_read_tokens == 800
    assert result.cost_usd > 0

    # second call fed the tool_result back to the model
    second = client.messages.calls[1]
    tool_result_msg = second["messages"][-1]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"][0]["type"] == "tool_result"


async def test_system_prompt_and_tools_are_cached():
    script = [_Resp([_text("hi")], "end_turn", _Usage(10, 5))]
    client = _FakeClient(script)
    provider = AnthropicProvider("k", DEFAULT_MODEL, client=client)
    await provider.complete_with_tools(
        [LLMMessage(role="system", content="BIG STABLE PROMPT"),
         LLMMessage(role="user", content="hi")],
        tools=TOOL_SCHEMAS, executor=execute_tool,
    )
    call = client.messages.calls[0]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["tools"][-1]["cache_control"] == {"type": "ephemeral"}


async def test_plain_complete_captures_usage_and_cost():
    script = [_Resp([_text("Great, which service?")], "end_turn", _Usage(50, 12))]
    provider = AnthropicProvider("k", "claude-opus-4-8", client=_FakeClient(script))
    result = await provider.complete([LLMMessage(role="user", content="hello")])
    assert result.text == "Great, which service?"
    assert result.tokens_in == 50 and result.tokens_out == 12
    assert result.cost_usd == costs.estimate_cost_usd("claude-opus-4-8", tokens_in=50, tokens_out=12)


async def test_loop_that_never_converges_raises():
    # Every response asks for another tool → exceeds max_iterations → raises so
    # the service layer can fall back to a safe deterministic reply.
    script = [
        _Resp([_tool_use("list_service_categories", {}, id=f"t{i}")], "tool_use", _Usage(5, 5))
        for i in range(10)
    ]
    provider = AnthropicProvider("k", DEFAULT_MODEL, client=_FakeClient(script))
    with pytest.raises(RuntimeError):
        await provider.complete_with_tools(
            [LLMMessage(role="user", content="hi")],
            tools=TOOL_SCHEMAS, executor=execute_tool, max_iterations=3,
        )


async def test_default_model_when_blank():
    provider = AnthropicProvider("k", "", client=_FakeClient([]))
    assert provider._model == DEFAULT_MODEL


# --- Cost table ------------------------------------------------------------
def test_cost_covers_cache_buckets_separately():
    c = costs.estimate_cost_usd(
        "claude-opus-4-8", tokens_in=1_000_000, tokens_out=0,
        cache_read_tokens=1_000_000, cache_write_tokens=1_000_000,
    )
    # 5.00 (input) + 0.50 (read @0.1x) + 6.25 (write @1.25x) = 11.75
    assert c == pytest.approx(11.75, rel=1e-6)


def test_cost_unknown_model_falls_back_not_zero():
    c = costs.estimate_cost_usd("some-future-model", tokens_in=1_000_000, tokens_out=0)
    assert c > 0


# --- Service-layer safety --------------------------------------------------
async def test_service_complete_with_tools_falls_back_on_provider_error(monkeypatch):
    class _Boom(LLMProvider):
        name = "boom"

        async def complete(self, messages, *, max_tokens=300):
            return LLMResult(text="mockfallback", provider="mock", model="mock-1")

        async def complete_with_tools(self, messages, *, tools, executor,
                                      max_tokens=400, max_iterations=5):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(llm_service, "_select_provider", lambda: _Boom())
    result, latency, success, err = await llm_service.complete_with_tools(
        [LLMMessage(role="user", content="hi")], tools=TOOL_SCHEMAS, executor=execute_tool,
    )
    assert success is False
    assert err is not None
    # fell back to the deterministic mock — customer still gets a safe reply
    assert result.text


async def test_service_mock_mode_ignores_tools(monkeypatch):
    # In mock mode complete_with_tools must behave exactly like complete().
    from settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    result, latency, success, err = await llm_service.complete_with_tools(
        [LLMMessage(role="system", content="Message intent: greeting."),
         LLMMessage(role="user", content="hi")],
        tools=TOOL_SCHEMAS, executor=execute_tool,
    )
    assert success is True
    assert result.provider == "mock"
    assert result.tool_calls == []
    get_settings.cache_clear()
