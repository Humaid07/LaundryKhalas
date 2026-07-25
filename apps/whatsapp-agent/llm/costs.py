"""Estimated LLM cost tracking (USD).

The agent persists per-reply token counts + an estimated cost so the team can
see spend without a separate billing integration (task spec §21, CLAUDE.md §11).
Costs are an ESTIMATE from a static price table — the authoritative figure is
always the Anthropic console. Prices are USD per 1M tokens.

Prompt caching changes the effective input price: a cache WRITE costs ~1.25x the
base input rate, a cache READ ~0.1x. We bill uncached input at the base rate,
cache writes at 1.25x and cache reads at 0.1x, matching Anthropic's model.
"""
from __future__ import annotations

# USD per 1,000,000 tokens: (input, output). Keep model ids exact — no date
# suffixes (see the Claude API reference). Unknown models fall back to the Opus
# rate so an estimate is never silently zero for a real call.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}

_DEFAULT_RATE = (5.00, 25.00)  # Opus-tier — conservative (never under-reports)

_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.10


def _rate(model: str) -> tuple[float, float]:
    if model in _PRICE_PER_MTOK:
        return _PRICE_PER_MTOK[model]
    # Tolerate a stray date suffix or vendor prefix without crashing an estimate.
    for known, rate in _PRICE_PER_MTOK.items():
        if known in model:
            return rate
    return _DEFAULT_RATE


def estimate_cost_usd(
    model: str,
    *,
    tokens_in: int,
    tokens_out: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimate the USD cost of one turn. ``tokens_in`` is the uncached input
    (Anthropic reports cache reads/writes separately from ``input_tokens``), so
    the three input buckets do not double-count."""
    in_rate, out_rate = _rate(model)
    cost = (
        tokens_in * in_rate
        + cache_write_tokens * in_rate * _CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * in_rate * _CACHE_READ_MULTIPLIER
        + tokens_out * out_rate
    ) / 1_000_000
    return round(cost, 6)
