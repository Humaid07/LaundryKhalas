"""Model selection + effective config for the WhatsApp runtime (offline).

Verifies the customer-facing runtime resolves to the pinned Claude Haiku 4.5 id,
that ANTHROPIC_WHATSAPP_MODEL is the single source of truth (overriding the legacy
knobs), that extended thinking stays off, and that only one sampling parameter is
ever sent — with no hidden Sonnet fallback on the happy path.
"""
from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import LLMMessage
from settings import Settings

HAIKU = "claude-haiku-4-5"


def test_whatsapp_model_overrides_legacy_knobs():
    s = Settings(anthropic_whatsapp_model=HAIKU, anthropic_model="claude-sonnet-5",
                 llm_model="claude-sonnet-5")
    assert s.anthropic_model_effective == HAIKU


def test_falls_back_through_anthropic_then_llm_model():
    # Clear the WhatsApp override (populated from .env) to exercise the fallback chain.
    assert Settings(anthropic_whatsapp_model="",
                    anthropic_model="claude-opus-4-8").anthropic_model_effective == "claude-opus-4-8"
    assert Settings(anthropic_whatsapp_model="", anthropic_model="",
                    llm_model=HAIKU).anthropic_model_effective == HAIKU


def test_extended_thinking_off_by_default_and_not_sent():
    s = Settings(anthropic_whatsapp_model=HAIKU)
    assert s.anthropic_extended_thinking is False
    provider = AnthropicProvider("k", s.anthropic_model_effective,
                                 extended_thinking=s.anthropic_extended_thinking)
    kwargs = provider._base_kwargs(None)
    assert "thinking" not in kwargs


def test_only_one_sampling_param_and_haiku_gets_temperature():
    # Haiku accepts sampling params, so temperature (and nothing else) is sent.
    provider = AnthropicProvider("k", HAIKU, temperature=0.2)
    kwargs = provider._base_kwargs(None)
    assert kwargs["temperature"] == 0.2
    assert "top_p" not in kwargs and "top_k" not in kwargs


def test_effective_temperature_prefers_whatsapp_value():
    assert Settings(anthropic_whatsapp_temperature=0.4,
                    anthropic_temperature=0.2).anthropic_temperature_effective == 0.4
    # blank/<0 → falls back to the generic temperature
    assert Settings(anthropic_whatsapp_temperature=-1.0,
                    anthropic_temperature=0.3).anthropic_temperature_effective == 0.3


def test_ai_status_exposes_effective_model_for_diagnostics():
    status = Settings(ai_provider="anthropic", anthropic_api_key="x",
                      anthropic_whatsapp_model=HAIKU).ai_status
    assert status["model"] == HAIKU
    assert status["extended_thinking"] is False
    assert status["prompt_cache_enabled"] is True


def test_no_sonnet_reference_in_effective_config():
    s = Settings(anthropic_whatsapp_model=HAIKU)
    assert "sonnet" not in s.anthropic_model_effective


def test_validate_ai_config_accepts_haiku_setup():
    s = Settings(ai_provider="anthropic", anthropic_api_key="x",
                 anthropic_whatsapp_model=HAIKU)
    s.validate_ai_config()  # must not raise


async def test_model_carried_onto_result():
    from tests._fake_anthropic import FakeClient, Resp, Usage, text
    provider = AnthropicProvider("k", HAIKU,
                                 client=FakeClient([Resp([text("hi")], "end_turn", Usage(5, 2))]))
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.model == HAIKU
