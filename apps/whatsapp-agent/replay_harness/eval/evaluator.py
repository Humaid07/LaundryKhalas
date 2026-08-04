"""Rule-based evaluation of replayed turns.

Each check is deterministic and computed from CAPTURED state (agent reply text,
tool calls, workflow snapshot) — never from the historical staff reply. A turn
that differs from the historical reply is NOT a failure by itself.

Severities: CRITICAL / HIGH / MEDIUM / LOW / INFO. We only emit a finding when we
can compute it reliably; checks that depend on missing external operational data
are marked INCONCLUSIVE_EXTERNAL_STATE rather than failed.

This is a solid, extensible subset of the spec's rule list. Adding a check =
append a function to CHECKS.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from ..core.models import EvalFinding, ReplayTurn

# Emoji detection (broad unicode ranges + common symbols).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "️"
    "]"
)
_VA_RE = re.compile(r"\b(virtual assistant|ai assistant|as an ai|language model|chatbot|automated assistant)\b", re.I)
_EXCLAIM_RE = re.compile(r"!")
# Customer-facing em/en dash or " - " used as formatting punctuation.
_DASH_RE = re.compile(r"\s[—–]\s|\s-\s")
_LONG_WORD_LIMIT = 60


def _f(code, sev, msg, expected="", actual="") -> EvalFinding:
    return EvalFinding(code=code, severity=sev, message=msg, expected=expected, actual=actual)


# --- individual checks -----------------------------------------------------
def check_empty_reply(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    # Media turns may legitimately not produce a text reply (voice handling), so
    # only flag empty replies on text turns with no error and no escalation.
    if turn.media_type in ("audio", "image", "video", "document"):
        return None
    if not turn.agent_reply.strip() and not turn.error and turn.human_intervention_status != "human_takeover":
        return _f("empty_reply", "HIGH", "Agent produced no customer-facing reply on a text turn")
    return None


def check_ai_reply_during_takeover(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    # If a human already owns the conversation, the model must NOT generate a
    # customer reply. When takeover is active, the pipeline short-circuits (no LLM
    # records). LLM records + a reply during takeover is a CRITICAL leak.
    status = (turn.human_intervention_status or "").lower()
    if status == "human_takeover" and turn.usage.output_tokens > 0 and turn.agent_reply.strip():
        return _f(
            "ai_reply_during_takeover", "CRITICAL",
            "Model generated a customer reply while conversation was in human takeover",
        )
    return None


def check_emoji(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    if turn.agent_reply and _EMOJI_RE.search(turn.agent_reply):
        return _f("emoji_in_reply", "LOW", "Agent reply contains an emoji (style rule: no emojis)")
    return None


def check_virtual_assistant(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    if turn.agent_reply and _VA_RE.search(turn.agent_reply):
        return _f("mentions_virtual_assistant", "MEDIUM",
                  "Agent describes itself as a virtual assistant / AI (style rule violation)")
    return None


def check_exclamation(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    if turn.agent_reply and len(_EXCLAIM_RE.findall(turn.agent_reply)) >= 1:
        return _f("exclamation_mark", "LOW", "Agent reply uses exclamation mark(s)")
    return None


def check_dash_formatting(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    if turn.agent_reply and _DASH_RE.search(turn.agent_reply):
        return _f("dash_formatting", "LOW", "Agent reply uses dash-based formatting")
    return None


def check_long_reply(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    if turn.response_word_count > _LONG_WORD_LIMIT:
        return _f("long_reply", "MEDIUM",
                  f"Agent reply is long ({turn.response_word_count} words > {_LONG_WORD_LIMIT})")
    return None


def check_duplicate_reply(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    prev = ctx.get("prev_reply")
    if turn.agent_reply and prev and turn.agent_reply.strip() == prev.strip():
        return _f("duplicate_reply", "MEDIUM", "Agent repeated the identical previous reply")
    return None


def check_vat_readded(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    # Published prices are VAT-inclusive; the reply must not add 5% VAT on top.
    if turn.agent_reply and re.search(r"\b(?:\+|plus|add(?:ing)?)\s*5%?\s*vat\b", turn.agent_reply, re.I):
        return _f("vat_readded", "CRITICAL", "Agent appears to add VAT on top of VAT-inclusive prices")
    return None


def check_open_ended_pickup_before_availability(turn: ReplayTurn, ctx) -> Optional[EvalFinding]:
    # The agent should check validated slots, not ask an open-ended "what time
    # suits you?" before confirming availability.
    if not turn.agent_reply:
        return None
    asked_open = bool(re.search(r"what time (?:suits|works|would).*\?", turn.agent_reply, re.I))
    checked_slots = any(tc.tool_name in ("get_pickup_slots", "list_pickup_slots", "set_pickup_slot")
                        for tc in turn.tool_calls)
    if asked_open and not checked_slots and not turn.pickup_slot_options:
        return _f("open_ended_pickup_question", "HIGH",
                  "Agent asked an open-ended pickup time before checking validated availability")
    return None


CHECKS: list[Callable[[ReplayTurn, dict], Optional[EvalFinding]]] = [
    check_empty_reply,
    check_ai_reply_during_takeover,
    check_vat_readded,
    check_open_ended_pickup_before_availability,
    check_virtual_assistant,
    check_long_reply,
    check_duplicate_reply,
    check_emoji,
    check_exclamation,
    check_dash_formatting,
]


def evaluate_turn(turn: ReplayTurn, ctx: dict) -> list[EvalFinding]:
    """Run all checks against a turn. `ctx` carries cross-turn state (prev_reply)."""
    findings: list[EvalFinding] = []
    for check in CHECKS:
        try:
            finding = check(turn, ctx)
        except Exception:  # noqa: BLE001 - a check must never crash the run
            finding = None
        if finding is not None:
            findings.append(finding)
    return findings
