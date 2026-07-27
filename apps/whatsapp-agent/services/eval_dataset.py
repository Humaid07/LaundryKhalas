"""Structured evaluation-dataset format + loader/validator.

Historical chats are converted into SANITISED, structured eval records (never
used as a raw prompt corpus). Each record captures the situation, the expected
extraction/tools/response, and the FORBIDDEN behaviour — the target being the
approved business rules + desired style, NOT a copy of past agent behaviour.

This module defines the record schema, the evaluation groups, a validator, and a
loader for ``eval/evaluation_dataset.json`` (a small set of synthesised, PII-free
seed examples; the full set is generated from history via ``services/sanitize``).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from services import sanitize

_DATASET_FILE = Path(__file__).resolve().parent.parent / "eval" / "evaluation_dataset.json"

# The evaluation groups (spec). Every record must belong to exactly one.
EVAL_GROUPS = frozenset({
    "successful_booking", "price_enquiry_converted", "price_enquiry_not_converted",
    "booking_abandoned", "repeat_customer", "discount_request", "campaign_response",
    "bespoke_service", "photo_required", "location_required", "facility_quotation",
    "complaint", "cancellation", "order_edit", "order_status", "b2b_lead",
    "prompt_injection", "provider_failure", "duplicate_message", "fragmented_messages",
})

# Required keys on every eval record.
_REQUIRED = frozenset({
    "id", "group", "intent", "message_fragments", "combined_turn",
    "expected_extracted_fields", "expected_tool_calls", "expected_response",
    "forbidden_response_behaviour", "funnel_stage", "service_category",
    "country", "outcome",
})

# Fields that would carry PII if present — must be absent (records ship sanitised).
_FORBIDDEN_KEYS = frozenset({
    "phone", "phone_e164", "customer_phone", "email", "pickup_address",
    "address", "payment_method", "media_url", "api_key",
})


def validate_record(record: dict) -> list[str]:
    """Return a list of validation errors ([] when valid)."""
    errors: list[str] = []
    missing = _REQUIRED - set(record.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    leaked = _FORBIDDEN_KEYS & set(record.keys())
    if leaked:
        errors.append(f"PII keys present: {sorted(leaked)}")
    grp = record.get("group")
    if grp not in EVAL_GROUPS:
        errors.append(f"unknown group: {grp}")
    if not isinstance(record.get("message_fragments"), list):
        errors.append("message_fragments must be a list")
    if not isinstance(record.get("expected_tool_calls"), list):
        errors.append("expected_tool_calls must be a list")
    return errors


def to_eval_record(*, id: str, group: str, intent: str, message_fragments: list[str],
                   expected_extracted_fields: dict, expected_tool_calls: list[str],
                   expected_response: str, forbidden_response_behaviour: list[str],
                   funnel_stage: str, service_category: str | None, country: str,
                   outcome: str, names: list[str] | None = None) -> dict:
    """Build a SANITISED eval record from raw parts (fragments + response scrubbed)."""
    frags = [sanitize.sanitize_text(f, mask_names=bool(names), names=names)
             for f in message_fragments]
    return {
        "id": id, "group": group, "intent": intent,
        "message_fragments": frags,
        "combined_turn": " ".join(frags).strip(),
        "expected_extracted_fields": expected_extracted_fields,
        "expected_tool_calls": expected_tool_calls,
        "expected_response": sanitize.sanitize_text(
            expected_response, mask_names=bool(names), names=names),
        "forbidden_response_behaviour": forbidden_response_behaviour,
        "funnel_stage": funnel_stage, "service_category": service_category,
        "country": country, "outcome": outcome,
    }


@lru_cache(maxsize=1)
def load_dataset() -> list[dict]:
    if not _DATASET_FILE.exists():
        return []
    with _DATASET_FILE.open(encoding="utf-8") as fh:
        return json.load(fh).get("records", [])


def dataset_groups() -> set[str]:
    return {r.get("group") for r in load_dataset()}
