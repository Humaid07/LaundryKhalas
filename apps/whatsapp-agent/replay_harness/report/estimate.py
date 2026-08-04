"""Dry-run cost/token/runtime estimate (no LLM calls).

Estimates are deliberately conservative and clearly approximate. Real cost is
always taken from actual Anthropic usage fields after the run (see cost_report).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.models import Conversation
from ..runner.grouping import group_turns

# Approximate Claude Sonnet 5 rates (USD per 1M tokens). Used ONLY for the
# pre-run estimate; final numbers come from real usage.
_RATE_INPUT = 3.0
_RATE_OUTPUT = 15.0
_RATE_CACHE_READ = 0.30

# Rough per-turn token assumptions with prompt caching:
#   most of the ~4k-token system+tools prompt is served from cache after turn 1.
_ASSUMED_FRESH_INPUT_TOKENS = 900      # uncached portion (history + user text)
_ASSUMED_CACHE_READ_TOKENS = 3500      # cached system + tools
_ASSUMED_OUTPUT_TOKENS = 120
_ASSUMED_TOOL_ROUNDS = 1.6             # avg model round-trips per turn
_ASSUMED_SECONDS_PER_TURN = 3.5


@dataclass
class Estimate:
    conversations: int
    inbound_messages: int
    turns: int
    model_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    estimated_cost_usd: float
    estimated_runtime_seconds: float
    concurrency: int

    def as_dict(self) -> dict:
        return {
            "conversations": self.conversations,
            "inbound_messages": self.inbound_messages,
            "turns": self.turns,
            "model_calls": self.model_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 2),
            "estimated_runtime_minutes": round(self.estimated_runtime_seconds / 60, 1),
            "concurrency": self.concurrency,
        }


def estimate(conversations: list[Conversation], *, concurrency: int = 5) -> Estimate:
    total_turns = 0
    total_inbound = 0
    for conv in conversations:
        total_inbound += conv.inbound_count
        total_turns += len(group_turns(conv.messages))

    model_calls = int(total_turns * _ASSUMED_TOOL_ROUNDS)
    input_tokens = int(total_turns * _ASSUMED_FRESH_INPUT_TOKENS * _ASSUMED_TOOL_ROUNDS)
    cache_read = int(total_turns * _ASSUMED_CACHE_READ_TOKENS * _ASSUMED_TOOL_ROUNDS)
    output_tokens = int(total_turns * _ASSUMED_OUTPUT_TOKENS * _ASSUMED_TOOL_ROUNDS)

    cost = (
        input_tokens / 1_000_000 * _RATE_INPUT
        + output_tokens / 1_000_000 * _RATE_OUTPUT
        + cache_read / 1_000_000 * _RATE_CACHE_READ
    )
    runtime = total_turns * _ASSUMED_SECONDS_PER_TURN / max(1, concurrency)
    return Estimate(
        conversations=len(conversations),
        inbound_messages=total_inbound,
        turns=total_turns,
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        estimated_cost_usd=cost,
        estimated_runtime_seconds=runtime,
        concurrency=concurrency,
    )
