"""CSV / JSONL / failed-export / cost report writers.

PII redaction is applied to all customer/agent free-text fields in the CSV/JSONL
outputs when cfg.redact_pii is true (the default).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from ..core.config import ReplayConfig
from ..core.models import ModelUsage, ReplayConversationResult, ReplayTurn
from ..core.pii import redact_text


def _r(text: str, cfg: ReplayConfig) -> str:
    return redact_text(text or "", enabled=cfg.redact_pii)


# --- summary CSV (one row per conversation) --------------------------------
def write_summary_csv(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "replay_run_id", "source_chat_id", "category", "inbound_message_count",
            "agent_reply_count", "historical_outbound_count", "final_state",
            "order_confirmed", "critical_failures", "high_failures", "medium_failures",
            "low_failures", "divergence_count", "average_reply_words", "maximum_reply_words",
            "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens",
            "estimated_cost_usd", "duration_seconds", "overall_result",
        ])
        for r in results:
            u = r.usage_total
            w.writerow([
                r.replay_run_id, r.source_chat_id, r.category, len(r.turns),
                r.agent_reply_count, r.historical_outbound_count, r.final_order_state,
                r.order_confirmed, r.critical_failures, r.high_failures, r.medium_failures,
                r.low_failures, r.divergence_count, r.average_reply_words, r.maximum_reply_words,
                u.input_tokens, u.output_tokens, u.cache_read_input_tokens,
                u.cache_creation_input_tokens, round(u.estimated_cost_usd, 6),
                r.duration_seconds, r.overall_result,
            ])


# --- turn CSV (one row per replayed turn) ----------------------------------
def write_turns_csv(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "source_chat_id", "turn_index", "customer_message", "agent_reply",
            "historical_reply", "intent", "service", "item", "price", "discount",
            "state_before", "state_after", "tool_calls", "divergence",
            "evaluation_result", "severity", "latency_ms", "cost_usd",
        ])
        for r in results:
            for t in r.turns:
                w.writerow([
                    t.source_chat_id, t.turn_index, _r(t.customer_message, cfg),
                    _r(t.agent_reply, cfg), _r(t.historical_reply, cfg), t.detected_intent,
                    t.resolved_service, t.resolved_item, t.final_total, t.discount_amount,
                    t.order_state_before, t.order_state_after,
                    ";".join(tc.tool_name for tc in t.tool_calls),
                    (t.divergence.divergence_type if t.divergence else ""),
                    ("PASS" if not t.findings else "FAIL"), t.worst_severity(),
                    t.usage.latency_ms, round(t.usage.estimated_cost_usd, 6),
                ])


# --- JSONL -----------------------------------------------------------------
def _turn_dict(t: ReplayTurn, cfg: ReplayConfig) -> dict:
    return {
        "turn_index": t.turn_index,
        "customer_message": _r(t.customer_message, cfg),
        "customer_fragments": [_r(x, cfg) for x in t.customer_fragments],
        "agent_reply": _r(t.agent_reply, cfg),
        "historical_reply": _r(t.historical_reply, cfg),
        "media_type": t.media_type,
        "media_available": t.media_available,
        "workflow": {
            "resolved_service": t.resolved_service,
            "service_code": t.service_code,
            "order_state_before": t.order_state_before,
            "order_state_after": t.order_state_after,
            "final_total": t.final_total,
            "pre_discount_total": t.pre_discount_total,
            "discount_amount": t.discount_amount,
            "discount_percentage": t.discount_percentage,
            "selected_pickup_slot": t.selected_pickup_slot,
            "pickup_slot_options": t.pickup_slot_options,
            "facility_selection_result": t.facility_selection_result,
            "additional_notes": _r(t.additional_notes, cfg),
            "confirmation_status": t.confirmation_status,
            "human_intervention_status": t.human_intervention_status,
            "catalogue_version": t.catalogue_version,
        },
        "style": {
            "word_count": t.response_word_count,
            "char_count": t.response_character_count,
            "emoji_removed": t.emoji_removed,
            "dash_normalized": t.dash_normalized,
            "exclamation_normalized": t.exclamation_normalized,
        },
        "tool_calls": [
            {"name": tc.tool_name, "arguments": tc.validated_arguments,
             "result_summary": _r(tc.safe_result_summary, cfg), "success": tc.success,
             "failure_type": tc.failure_type, "state_changed": tc.state_changed}
            for tc in t.tool_calls
        ],
        "usage": {
            "model_id": t.usage.model_id,
            "input_tokens": t.usage.input_tokens,
            "output_tokens": t.usage.output_tokens,
            "cache_read_input_tokens": t.usage.cache_read_input_tokens,
            "cache_creation_input_tokens": t.usage.cache_creation_input_tokens,
            "latency_ms": t.usage.latency_ms,
            "stop_reason": t.usage.stop_reason,
            "tool_loop_rounds": t.usage.tool_loop_rounds,
            "estimated_cost_usd": t.usage.estimated_cost_usd,
        },
        "findings": [
            {"code": fnd.code, "severity": fnd.severity, "message": fnd.message,
             "expected": fnd.expected, "actual": fnd.actual}
            for fnd in t.findings
        ],
        "divergence": (
            {"type": t.divergence.divergence_type,
             "agent_requested_field": t.divergence.agent_requested_field,
             "historical_customer_message": _r(t.divergence.historical_customer_message, cfg)}
            if t.divergence else None
        ),
        "error": t.error,
    }


def _conv_dict(r: ReplayConversationResult, cfg: ReplayConfig) -> dict:
    u = r.usage_total
    return {
        "replay_run_id": r.replay_run_id,
        "source_archive": r.source_archive,
        "source_chat_id": r.source_chat_id,
        "synthetic_customer_id": r.synthetic_customer_id,
        "synthetic_conversation_id": r.synthetic_conversation_id,
        "category": r.category,
        "replay_status": r.replay_status,
        "overall_result": r.overall_result,
        "final_order_state": r.final_order_state,
        "order_confirmed": r.order_confirmed,
        "critical_failures": r.critical_failures,
        "high_failures": r.high_failures,
        "medium_failures": r.medium_failures,
        "low_failures": r.low_failures,
        "divergence_count": r.divergence_count,
        "historical_outbound_count": r.historical_outbound_count,
        "usage_total": {
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "cache_read_input_tokens": u.cache_read_input_tokens,
            "cache_creation_input_tokens": u.cache_creation_input_tokens,
            "estimated_cost_usd": round(u.estimated_cost_usd, 6),
        },
        "duration_seconds": r.duration_seconds,
        "error": r.error,
        "turns": [_turn_dict(t, cfg) for t in r.turns],
    }


def write_conversations_jsonl(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(_conv_dict(r, cfg), default=str) + "\n")


def write_turns_jsonl(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in results:
            for t in r.turns:
                row = {"source_chat_id": r.source_chat_id, "category": r.category, **_turn_dict(t, cfg)}
                f.write(json.dumps(row, default=str) + "\n")


# --- failed conversations export -------------------------------------------
def write_failed_exports(results: list[ReplayConversationResult], base: Path, cfg: ReplayConfig) -> dict:
    counts = {"critical": 0, "high": 0, "medium": 0}
    for r in results:
        sev = None
        if r.critical_failures:
            sev = "critical"
        elif r.high_failures:
            sev = "high"
        elif r.medium_failures:
            sev = "medium"
        if sev is None:
            continue
        d = base / "failed_conversations" / sev
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{_safe(r.source_chat_id)}.json").write_text(
            json.dumps(_conv_dict(r, cfg), indent=2, default=str), encoding="utf-8"
        )
        counts[sev] += 1
    return counts


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "+._-" else "_" for c in name)


# --- critical failures CSV -------------------------------------------------
def write_critical_failures_csv(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "chat_id", "turn_index", "customer_message", "agent_response",
            "failure_type", "expected_rule", "actual_result", "tool_data",
            "suggested_investigation",
        ])
        for r in results:
            for t in r.turns:
                for fnd in t.findings:
                    if fnd.severity != "CRITICAL":
                        continue
                    w.writerow([
                        r.source_chat_id, t.turn_index, _r(t.customer_message, cfg),
                        _r(t.agent_reply, cfg), fnd.code, fnd.message or fnd.expected,
                        fnd.actual, ";".join(tc.tool_name for tc in t.tool_calls),
                        f"Review {fnd.code} in conversation {r.source_chat_id} turn {t.turn_index}",
                    ])


# --- cost report -----------------------------------------------------------
def write_cost_reports(results: list[ReplayConversationResult], out_csv: Path,
                       out_json: Path, cfg: ReplayConfig) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    per_category: dict[str, ModelUsage] = {}
    grand = ModelUsage()
    confirmed_cost = 0.0
    confirmed_count = 0
    rows = []
    for r in results:
        u = r.usage_total
        grand.add(u)
        per_category.setdefault(r.category, ModelUsage()).add(u)
        if r.order_confirmed:
            confirmed_cost += u.estimated_cost_usd
            confirmed_count += 1
        rows.append((r.source_chat_id, r.category, u))

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "key", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_creation_tokens", "estimated_cost_usd"])
        for chat_id, cat, u in sorted(rows, key=lambda x: -x[2].estimated_cost_usd):
            w.writerow(["conversation", chat_id, u.input_tokens, u.output_tokens,
                        u.cache_read_input_tokens, u.cache_creation_input_tokens,
                        round(u.estimated_cost_usd, 6)])
        for cat, u in sorted(per_category.items(), key=lambda x: -x[1].estimated_cost_usd):
            w.writerow(["category", cat, u.input_tokens, u.output_tokens,
                        u.cache_read_input_tokens, u.cache_creation_input_tokens,
                        round(u.estimated_cost_usd, 6)])

    most_expensive = sorted(rows, key=lambda x: -x[2].estimated_cost_usd)[:10]
    cache_read = grand.cache_read_input_tokens
    summary = {
        "model": cfg.model,
        "total_input_tokens": grand.input_tokens,
        "total_output_tokens": grand.output_tokens,
        "total_cache_read_tokens": grand.cache_read_input_tokens,
        "total_cache_creation_tokens": grand.cache_creation_input_tokens,
        "total_estimated_cost_usd": round(grand.estimated_cost_usd, 4),
        "average_cost_per_conversation": round(
            grand.estimated_cost_usd / len(results), 6) if results else 0,
        "average_cost_per_confirmed_booking": round(
            confirmed_cost / confirmed_count, 6) if confirmed_count else None,
        "confirmed_bookings": confirmed_count,
        "prompt_cache_read_tokens": cache_read,
        "per_category": {
            cat: round(u.estimated_cost_usd, 4) for cat, u in per_category.items()
        },
        "most_expensive_conversations": [
            {"chat_id": cid, "cost_usd": round(u.estimated_cost_usd, 6)}
            for cid, _cat, u in most_expensive
        ],
    }
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
