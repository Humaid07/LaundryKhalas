"""Prompt-cache structure for the WhatsApp runtime (offline, scripted client).

Asserts the mixed cache strategy (spec 2026-07-31):
  * 1h ephemeral cache on the stable system prompt AND the tool definitions
  * 5m ephemeral cache breakpoint on the last conversation-history turn
  * dynamic backend state + the newest customer message sit AFTER the last
    breakpoint (uncached), so they never invalidate the shared prefix
  * the shared stable prefix is byte-identical across customers/personas
  * usage fields (incl. per-TTL cache-creation split) are captured
  * disabling the cache emits NO cache_control anywhere (rollback)
"""
from agents.whatsapp_agent.context_assembly import build_cached_messages
from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import LLMMessage
from tests._fake_anthropic import FakeClient, Resp, Usage, text

HAIKU = "claude-haiku-4-5"
_TOOLS = [{"name": "a", "description": "x", "input_schema": {"type": "object"}},
          {"name": "b", "description": "y", "input_schema": {"type": "object"}}]


def _provider(script, **kw):
    return AnthropicProvider("k", HAIKU, client=FakeClient(script), **kw)


def _messages():
    return build_cached_messages(
        system_prompt="A" * 200,
        history=[("customer", "hi"), ("agent", "hello, how can I help?")],
        dynamic_state='{"workflow_state": "new", "persona": "Sara"}',
        user_text="I need a wash and fold",
    )


# --- assembler ---------------------------------------------------------------
def test_assembler_places_breakpoints():
    msgs = _messages()
    assert msgs[0].role == "system" and msgs[0].cache == "1h"
    # last history turn carries the 5m breakpoint
    history_turns = [m for m in msgs[1:-1]]
    assert history_turns[-1].cache == "5m"
    # dynamic state + newest message are the FINAL turn, uncached
    assert msgs[-1].cache is None
    assert "persona" in msgs[-1].content and "wash and fold" in msgs[-1].content


def test_assembler_no_history_still_caches_system():
    msgs = build_cached_messages(system_prompt="S" * 200, history=[],
                                 dynamic_state=None, user_text="hi")
    assert msgs[0].cache == "1h"
    assert all(m.cache is None for m in msgs[1:])


# --- provider wire shape -----------------------------------------------------
async def test_wire_prompt_has_1h_system_5m_history_and_beta_header():
    provider = _provider([Resp([text("ok")], "end_turn", Usage(10, 5, cw=5000, cw1=5000))])
    await provider.complete_with_tools(_messages(), tools=_TOOLS, executor=_noop)
    call = provider._client.messages.calls[0]

    assert call["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert call["tools"][-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert call["extra_headers"]["anthropic-beta"] == "extended-cache-ttl-2025-04-11"

    # exactly one 5m breakpoint, on a history turn; the final turn is uncached
    five_min = [m for m in call["messages"]
                if isinstance(m["content"], list)
                and m["content"][0].get("cache_control") == {"type": "ephemeral"}]
    assert len(five_min) == 1
    assert isinstance(call["messages"][-1]["content"], str)  # newest msg uncached


async def test_dynamic_state_is_after_last_breakpoint():
    provider = _provider([Resp([text("ok")], "end_turn", Usage(1, 1))])
    await provider.complete_with_tools(_messages(), tools=_TOOLS, executor=_noop)
    call = provider._client.messages.calls[0]
    # dynamic persona/state must NOT appear in the cached system block
    assert "persona" not in call["system"][0]["text"]
    assert "persona" in call["messages"][-1]["content"]


async def test_usage_split_captured():
    provider = _provider([Resp([text("ok")], "end_turn", Usage(10, 5, cr=4000, cw=5000, cw5=0, cw1=5000))])
    result = await provider.complete_with_tools(_messages(), tools=_TOOLS, executor=_noop)
    assert result.cache_read_tokens == 4000
    assert result.cache_write_tokens == 5000
    assert result.cache_write_1h_tokens == 5000
    assert result.cache_hit is True
    assert result.total_input_tokens == 10 + 4000 + 5000


async def test_persona_isolation_shared_prefix_is_identical():
    # Two customers with DIFFERENT personas must share a byte-identical cached
    # prefix (system + tools); only the final uncached turn differs.
    def build(persona, msg):
        return build_cached_messages(
            system_prompt="A" * 200, history=[("customer", "hi")],
            dynamic_state='{"persona": "%s"}' % persona, user_text=msg)

    p1 = _provider([Resp([text("ok")], "end_turn", Usage(1, 1))])
    await p1.complete_with_tools(build("Sara", "one"), tools=_TOOLS, executor=_noop)
    p2 = _provider([Resp([text("ok")], "end_turn", Usage(1, 1))])
    await p2.complete_with_tools(build("Maya", "two"), tools=_TOOLS, executor=_noop)

    c1, c2 = p1._client.messages.calls[0], p2._client.messages.calls[0]
    assert c1["system"] == c2["system"]          # identical stable prefix
    assert c1["tools"] == c2["tools"]
    assert "Sara" in c1["messages"][-1]["content"]
    assert "Maya" in c2["messages"][-1]["content"]
    assert c1["messages"][-1]["content"] != c2["messages"][-1]["content"]


async def test_cache_disabled_emits_no_cache_control():
    provider = _provider([Resp([text("ok")], "end_turn", Usage(1, 1))],
                         prompt_cache_enabled=False)
    await provider.complete_with_tools(_messages(), tools=_TOOLS, executor=_noop)
    call = provider._client.messages.calls[0]
    assert "cache_control" not in call["system"][0]
    assert "cache_control" not in call["tools"][-1]
    assert "extra_headers" not in call
    assert all(isinstance(m["content"], str) for m in call["messages"])


async def test_refusal_stop_reason_raises():
    import pytest
    provider = _provider([Resp([text("")], "refusal", Usage(1, 0))])
    with pytest.raises(RuntimeError):
        await provider.complete_with_tools(_messages(), tools=_TOOLS, executor=_noop)


async def _noop(name, tool_input):
    return "{}", False
