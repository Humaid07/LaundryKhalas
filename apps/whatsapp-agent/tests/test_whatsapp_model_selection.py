"""Model selection + Sonnet 5 request config for the WhatsApp runtime (offline).

Decision 2026-08-05: the customer-facing runtime is claude-sonnet-5 (was Haiku 4.5).
This suite verifies:
  * ANTHROPIC_WHATSAPP_MODEL is the single source of truth (overrides legacy knobs);
  * the Sonnet 5 request is built correctly — adaptive thinking + output_config.effort,
    and NO sampling params (temperature/top_p/top_k) and NO manual thinking budget
    (all of which 400 on Sonnet 5);
  * effort/thinking are NEVER sent to Haiku (they would 400 there);
  * there is no silent fallback to Haiku or a different Sonnet version.
"""
from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import LLMMessage
from settings import Settings

SONNET = "claude-sonnet-5"
HAIKU = "claude-haiku-4-5"


def _s(**kw) -> Settings:
    # _env_file=None → ignore any real .env so these are hermetic.
    return Settings(_env_file=None, **kw)


# --- model resolution --------------------------------------------------------
def test_whatsapp_model_overrides_legacy_knobs():
    s = _s(anthropic_whatsapp_model=SONNET, anthropic_model="claude-opus-4-8",
           llm_model="claude-haiku-4-5")
    assert s.anthropic_model_effective == SONNET


def test_falls_back_through_anthropic_then_llm_model():
    # Clear the WhatsApp override to exercise the fallback chain.
    assert _s(anthropic_whatsapp_model="",
              anthropic_model="claude-opus-4-8").anthropic_model_effective == "claude-opus-4-8"
    assert _s(anthropic_whatsapp_model="", anthropic_model="",
              llm_model=SONNET).anthropic_model_effective == SONNET


def test_runtime_default_is_never_a_silent_haiku():
    # With nothing configured the resolved id is the deliberate default (opus-4-8),
    # NEVER Haiku behind the operator's back.
    assert "haiku" not in _s(anthropic_whatsapp_model="", anthropic_model="",
                             llm_model="").anthropic_model_effective


# --- Sonnet 5 request shape --------------------------------------------------
def test_sonnet5_sends_effort_and_adaptive_thinking_no_sampling():
    provider = AnthropicProvider("k", SONNET, effort="high",
                                 thinking_mode="adaptive", thinking_display="omitted")
    kwargs = provider._base_kwargs(None)
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["thinking"] == {"type": "adaptive", "display": "omitted"}
    # Sonnet 5 rejects sampling params — none may ever be sent.
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs and "top_k" not in kwargs
    # No manual/budget-style thinking either.
    assert "budget_tokens" not in kwargs.get("thinking", {})


def test_effort_and_thinking_never_sent_to_haiku():
    # Even when effort is configured, it (and thinking) must NOT reach Haiku, which
    # accepts sampling params instead and would 400 on effort/adaptive thinking.
    provider = AnthropicProvider("k", HAIKU, effort="high",
                                 thinking_mode="adaptive", temperature=0.2)
    kwargs = provider._base_kwargs(None)
    assert kwargs["temperature"] == 0.2
    assert "output_config" not in kwargs
    assert "thinking" not in kwargs
    assert "top_p" not in kwargs and "top_k" not in kwargs


async def test_sonnet5_effort_recorded_on_result():
    from tests._fake_anthropic import FakeClient, Resp, Usage, text
    provider = AnthropicProvider("k", SONNET, effort="high",
                                 client=FakeClient([Resp([text("hi")], "end_turn", Usage(5, 2))]))
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.model == SONNET
    assert result.effort == "high"


async def test_haiku_effort_is_none_on_result():
    from tests._fake_anthropic import FakeClient, Resp, Usage, text
    provider = AnthropicProvider("k", HAIKU, effort="high",
                                 client=FakeClient([Resp([text("hi")], "end_turn", Usage(5, 2))]))
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.effort is None  # not applicable → distinguishable from "high"


# --- no silent live fallback -------------------------------------------------
def test_no_live_fallback_model_by_default():
    assert _s().anthropic_fallback_model_effective == ""


def test_fallback_requires_explicit_model_and_enable():
    # Enabled but no id → still no fallback, and validation rejects the config.
    s = _s(ai_provider="anthropic", anthropic_api_key="k", anthropic_fallback_enabled=True)
    assert s.anthropic_fallback_model_effective == ""
    import pytest
    with pytest.raises(ValueError):
        s.validate_ai_config()
    # Enabled WITH an explicit id → that id is used.
    s2 = _s(anthropic_fallback_enabled=True, anthropic_fallback_model="claude-opus-4-8")
    assert s2.anthropic_fallback_model_effective == "claude-opus-4-8"


# --- effective config resolution + diagnostics -------------------------------
def test_effort_resolution_defaults_high_and_validates():
    assert _s().anthropic_whatsapp_effort_effective == "high"
    assert _s(anthropic_whatsapp_effort="MAX").anthropic_whatsapp_effort_effective == "max"
    # nonsense → safe default
    assert _s(anthropic_whatsapp_effort="bogus").anthropic_whatsapp_effort_effective == "high"


def test_ai_status_exposes_sonnet5_reasoning_and_ruleset():
    status = _s(ai_provider="anthropic", anthropic_api_key="x",
                anthropic_whatsapp_model=SONNET).ai_status
    assert status["model"] == SONNET
    assert status["effort"] == "high"
    assert status["thinking_mode"] == "adaptive"
    assert status["thinking_display"] == "omitted"
    assert status["fallback_model"] == ""
    assert status["ruleset_version"] == "2026_08_05"
    assert status["prompt_cache_enabled"] is True


def test_validate_ai_config_accepts_sonnet5_setup():
    s = _s(ai_provider="anthropic", anthropic_api_key="x", anthropic_whatsapp_model=SONNET)
    s.validate_ai_config()  # must not raise


def test_invalid_effort_or_thinking_rejected():
    import pytest
    with pytest.raises(ValueError):
        _s(ai_provider="anthropic", anthropic_api_key="k",
           anthropic_whatsapp_effort="turbo").validate_ai_config()
    with pytest.raises(ValueError):
        _s(ai_provider="anthropic", anthropic_api_key="k",
           anthropic_whatsapp_thinking_mode="enabled").validate_ai_config()
