"""Aggregate LLM cost + prompt-cache report (pure, divide-by-zero safe)."""
from services.metrics import build_llm_cost_report


def test_report_computes_rates_and_averages():
    r = build_llm_cost_report({
        "turns": 100, "conversations": 40,
        "input_tokens": 20_000, "output_tokens": 8_000,
        "cache_read_tokens": 500_000, "cache_creation_tokens": 40_000,
        "cache_hit_turns": 75, "cost_usd": 0.42,
        "haiku_error_turns": 2, "tool_validation_failures": 3,
        "human_intervention_conversations": 4, "style_normalized_turns": 5,
    })
    assert r["prompt_cache"]["hit_rate_pct"] == 75.0
    assert r["prompt_cache"]["miss_rate_pct"] == 25.0
    assert r["prompt_cache"]["cache_read_tokens"] == 500_000
    assert r["tokens"]["avg_input_tokens_per_conversation"] == 500.0
    assert r["cost"]["avg_cost_usd_per_conversation"] == round(0.42 / 40, 6)
    assert r["cost"]["avg_cost_usd_per_turn"] == round(0.42 / 100, 6)
    assert r["reliability"]["haiku_error_rate_pct"] == 2.0
    assert r["reliability"]["human_intervention_rate_pct"] == 10.0
    assert r["reliability"]["reply_style_normalization_rate_pct"] == 5.0


def test_report_is_zero_safe_on_empty():
    r = build_llm_cost_report({})
    assert r["prompt_cache"]["hit_rate_pct"] == 0.0
    assert r["prompt_cache"]["miss_rate_pct"] == 0.0
    assert r["cost"]["total_cost_usd"] == 0.0
    assert r["tokens"]["avg_input_tokens_per_conversation"] == 0.0
