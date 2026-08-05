"""Classifier — forced structured-output provider path + persistence contract.

The live Sonnet-5 path is exercised here OFFLINE by injecting a scripted fake
Anthropic client into AnthropicProvider (no key, no network), so we can assert the
forced-tool call is wired correctly (tool_choice, single call, parsed input +
usage/cost) without spending tokens. Persistence is asserted to be a safe no-op in
SQLite mode (the suite never touches asyncpg).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from classifier.schema import CLASSIFIER_TOOL_NAME, CLASSIFIER_TOOL_SCHEMA
from db.repositories import classifications_repo
from classifier.schema import Classification
from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import LLMMessage


class _FakeMessages:
    def __init__(self, response, capture):
        self._response = response
        self._capture = capture

    async def create(self, **kwargs):
        self._capture.update(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, capture):
        self.messages = _FakeMessages(response, capture)


def _tool_use_response(payload: dict):
    block = SimpleNamespace(type="tool_use", name=CLASSIFIER_TOOL_NAME, input=payload, id="tu_1")
    usage = SimpleNamespace(
        input_tokens=1200, output_tokens=40,
        cache_read_input_tokens=1000, cache_creation_input_tokens=0,
        cache_creation=None,
    )
    return SimpleNamespace(content=[block], usage=usage, stop_reason="tool_use", _request_id="req_1")


async def test_complete_structured_forces_tool_and_parses():
    capture: dict = {}
    payload = {"primary_intent": "PRICE_ENQUIRY", "service_domain": "SHOES",
               "intent_confidence": 0.95, "customer_goal": "GET_PRICE",
               "conversation_route": "MAIN_AGENT", "sentiment": "NEUTRAL",
               "urgency": "NORMAL", "requires_human": False,
               "needs_clarification": False, "should_cancel_followups": True}
    provider = AnthropicProvider(
        "unused-key", "claude-sonnet-5",
        client=_FakeClient(_tool_use_response(payload), capture),
        thinking_mode="off", effort="low",
    )
    result, parsed = await provider.complete_structured(
        [LLMMessage(role="system", content="SYS", cache="1h"),
         LLMMessage(role="user", content="{}")],
        tool=CLASSIFIER_TOOL_SCHEMA, tool_name=CLASSIFIER_TOOL_NAME, max_tokens=700,
    )
    # forced single tool
    assert capture["tool_choice"] == {"type": "tool", "name": CLASSIFIER_TOOL_NAME,
                                      "disable_parallel_tool_use": True}
    assert capture["max_tokens"] == 700
    # no sampling params for the adaptive family, and thinking disabled for the classifier
    assert "temperature" not in capture
    assert "thinking" not in capture
    # parsed structured output + usage/cost captured
    assert parsed["primary_intent"] == "PRICE_ENQUIRY"
    assert result.tokens_in == 1200 and result.cache_read_tokens == 1000
    assert result.cost_usd > 0
    c = Classification.from_tool_input(parsed)
    assert c.primary_intent == "PRICE_ENQUIRY" and c.service_domain == "SHOES"


async def test_complete_structured_raises_on_refusal():
    capture: dict = {}
    refusal = SimpleNamespace(content=[], usage=SimpleNamespace(
        input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
        cache_creation_input_tokens=0, cache_creation=None), stop_reason="refusal", _request_id="r")
    provider = AnthropicProvider("k", "claude-sonnet-5", client=_FakeClient(refusal, capture))
    with pytest.raises(RuntimeError):
        await provider.complete_structured(
            [LLMMessage(role="user", content="{}")],
            tool=CLASSIFIER_TOOL_SCHEMA, tool_name=CLASSIFIER_TOOL_NAME, max_tokens=700)


async def test_persistence_is_noop_in_sqlite_mode():
    # conftest pins DATABASE_MODE=sqlite → repo must no-op (never touch asyncpg)
    c = Classification(primary_intent="GREETING")
    row = await classifications_repo.insert_classification(
        c, conversation_id="x", customer_id="y", message_id="z",
        provider="evolution", provider_message_id="wa_1")
    assert row is None
    assert await classifications_repo.get_for_conversation("x") == []
    assert await classifications_repo.add_correction("id", corrected_by="ops") is None
