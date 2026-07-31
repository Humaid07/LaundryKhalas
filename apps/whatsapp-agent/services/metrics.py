"""Quality-metrics assembly (pure, deterministic).

Turns raw counts (gathered by ``db/repositories/metrics_repo.py``) into a
structured quality report with safe rates. All ratio math is divide-by-zero safe
and pure, so it's unit-testable without a database. B2B leads are excluded from
consumer conversion upstream (the repo filters them); this layer just assembles.

Do not optimise for shorter conversations — correctness/conversion/trust matter
more (spec). These metrics evaluate future prompt/model changes, not reward speed.
"""
from __future__ import annotations


def ratio(numerator, denominator) -> float:
    """Fraction 0.0–1.0, rounded to 4dp. 0.0 when the denominator is 0."""
    n = float(numerator or 0)
    d = float(denominator or 0)
    return round(n / d, 4) if d else 0.0


def pct(numerator, denominator) -> float:
    """Percentage 0.0–100.0, rounded to 1dp. 0.0 when the denominator is 0."""
    return round(ratio(numerator, denominator) * 100, 1)


def build_llm_cost_report(raw: dict) -> dict:
    """Assemble the prompt-cache + LLM-cost aggregate report from raw counts/sums
    (gathered from the persisted per-turn usage metadata). Pure and divide-by-zero
    safe. ``raw`` keys (all optional, default 0):

      turns, conversations, input_tokens, output_tokens, cache_read_tokens,
      cache_creation_tokens, cache_hit_turns, cost_usd, haiku_error_turns,
      tool_validation_failures, human_intervention_conversations, style_normalized_turns

    Cache hit rate uses actual Anthropic usage (a turn is a hit when it reported any
    cache_read tokens) — never estimated from prompt length. Cost uses the real
    per-turn estimate summed upstream from actual token buckets (see llm/costs.py)."""
    turns = int(raw.get("turns", 0) or 0)
    convos = int(raw.get("conversations", 0) or 0)
    input_tokens = int(raw.get("input_tokens", 0) or 0)
    output_tokens = int(raw.get("output_tokens", 0) or 0)
    cache_read = int(raw.get("cache_read_tokens", 0) or 0)
    cache_create = int(raw.get("cache_creation_tokens", 0) or 0)
    cache_hit_turns = int(raw.get("cache_hit_turns", 0) or 0)
    cost = float(raw.get("cost_usd", 0.0) or 0)

    return {
        "turns": turns,
        "conversations": convos,
        "prompt_cache": {
            "hit_rate_pct": pct(cache_hit_turns, turns),
            "miss_rate_pct": round(100.0 - pct(cache_hit_turns, turns), 1) if turns else 0.0,
            "cache_read_tokens": cache_read,
            "cache_creation_tokens": cache_create,
        },
        "tokens": {
            "avg_input_tokens_per_conversation": round(ratio(input_tokens, convos), 1),
            "avg_output_tokens_per_conversation": round(ratio(output_tokens, convos), 1),
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
        },
        "cost": {
            "total_cost_usd": round(cost, 6),
            "avg_cost_usd_per_conversation": round(ratio(cost, convos), 6),
            "avg_cost_usd_per_turn": round(ratio(cost, turns), 6),
        },
        "reliability": {
            "haiku_error_rate_pct": pct(raw.get("haiku_error_turns", 0), turns),
            "tool_validation_failure_rate_pct": pct(raw.get("tool_validation_failures", 0), turns),
            "human_intervention_rate_pct": pct(
                raw.get("human_intervention_conversations", 0), convos),
            "reply_style_normalization_rate_pct": pct(
                raw.get("style_normalized_turns", 0), turns),
        },
    }


def build_quality_report(raw: dict) -> dict:
    """Assemble the quality report from raw counts. ``raw`` keys (all optional,
    default 0) are the consumer/escalation counts + the by-dimension breakdowns.
    Consumer figures EXCLUDE B2B leads (filtered in the repo)."""
    c = raw.get("consumer", {})
    # Counts come back as ints; SQL sum()/revenue can be Decimal — coerce so the
    # arithmetic below never mixes float/Decimal.
    total_customers = int(c.get("total_customers", 0) or 0)
    with_confirmed = int(c.get("customers_with_confirmed", 0) or 0)
    repeat = int(c.get("repeat_customers", 0) or 0)
    booking_started = int(c.get("booking_started", 0) or 0)
    confirmed_orders = int(c.get("confirmed_orders", 0) or 0)
    price_enquiry = int(c.get("price_enquiry_customers", 0) or 0)
    lifetime_value = float(c.get("confirmed_revenue", 0.0) or 0)

    esc = raw.get("escalations", {})
    total_convos = esc.get("total_conversations", 0)
    flagged = esc.get("flagged_conversations", 0)

    return {
        "consumer": {
            "total_customers": total_customers,
            "customers_with_confirmed_order": with_confirmed,
            "repeat_customers": repeat,
            "repeat_customer_rate_pct": pct(repeat, with_confirmed),
            "confirmed_orders": confirmed_orders,
            "confirmed_revenue_aed": round(float(lifetime_value or 0), 2),
            "avg_order_value_aed": round(float(lifetime_value or 0) / confirmed_orders, 2)
            if confirmed_orders else 0.0,
            "conversion": {
                "price_enquiry_customers": price_enquiry,
                "booking_started": booking_started,
                "confirmed": confirmed_orders,
                "started_to_confirmed_rate_pct": pct(confirmed_orders, booking_started),
                "customer_conversion_rate_pct": pct(with_confirmed, total_customers),
            },
        },
        "escalations": {
            "total_conversations": total_convos,
            "flagged_conversations": flagged,
            "escalation_rate_pct": pct(flagged, total_convos),
            "open_complaints": esc.get("open_complaints", 0),
            "pending_tasks_open": esc.get("pending_tasks_open", 0),
            "pending_tasks_overdue": esc.get("pending_tasks_overdue", 0),
        },
        "b2b": {"open_leads": raw.get("b2b", {}).get("open_leads", 0)},
        "by_service": raw.get("by_service", []),
        "by_market": raw.get("by_market", []),
        "by_segment": raw.get("by_segment", []),
    }
