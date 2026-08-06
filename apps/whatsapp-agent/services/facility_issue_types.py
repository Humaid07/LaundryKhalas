"""Canonical facility issue-type registry (pure, backend-authoritative).

Each issue type carries its operational metadata: a human label, a default
severity/priority, whether it inherently needs a customer response, a photo, or a
price revision, and whether it PAUSES the order from advancing toward delivery
until resolved. The facility picks a type + writes an explanation; the backend
derives the flags here (a client may not silently escalate to a price revision).

Kept pure so it is unit-testable and shared by the API + serializer without a DB.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssueType:
    key: str
    label: str
    severity: str          # critical | high | medium
    priority: str          # urgent | high | normal
    requires_customer_response: bool = False
    requires_photo: bool = False
    requires_price_revision: bool = False
    blocking: bool = False  # pauses mark_ready / handoff until resolved


_TYPES: tuple[IssueType, ...] = (
    IssueType("ITEM_DIFFERS_FROM_DESCRIPTION", "Item differs from description", "high", "high",
              requires_customer_response=True, blocking=True),
    IssueType("PHOTO_REQUIRED", "Customer photo required", "medium", "normal", requires_photo=True),
    IssueType("MEASUREMENT_REQUIRED", "Measurement required", "medium", "normal"),
    IssueType("SPECIALIST_TREATMENT_REQUIRED", "Specialist treatment required", "high", "high",
              blocking=True),
    IssueType("EXISTING_DAMAGE_DETECTED", "Existing damage detected", "high", "high",
              requires_customer_response=True, requires_photo=True, blocking=True),
    IssueType("HEAVY_STAIN_DETECTED", "Heavy stain detected", "medium", "high",
              requires_customer_response=True),
    IssueType("MATERIAL_REQUIRES_REVIEW", "Material requires review", "medium", "high", blocking=True),
    IssueType("ALTERATION_CLARIFICATION_REQUIRED", "Alteration clarification required", "high", "high",
              requires_customer_response=True, blocking=True),
    IssueType("ALTERATION_PHOTO_REQUIRED", "Alteration photo required", "medium", "normal",
              requires_photo=True),
    IssueType("ALTERATION_NOT_STANDARD", "Alteration is not standard", "high", "high",
              requires_customer_response=True, requires_price_revision=True, blocking=True),
    IssueType("ALTERATION_TECHNICIAN_REVIEW", "Alteration technician review", "high", "high",
              blocking=True),
    IssueType("PRICE_REVISION_REQUIRED", "Price revision required", "high", "urgent",
              requires_customer_response=True, requires_price_revision=True, blocking=True),
    IssueType("SERVICE_NOT_SUPPORTED", "Service not supported", "high", "high", blocking=True),
    IssueType("ADDITIONAL_PROCESSING_REQUIRED", "Additional processing required", "medium", "high",
              requires_price_revision=True, blocking=True),
    IssueType("UNABLE_TO_MEET_TURNAROUND", "Unable to meet turnaround", "high", "urgent",
              requires_customer_response=True),
    IssueType("MISSING_ITEM", "Missing item", "critical", "urgent",
              requires_customer_response=True, blocking=True),
    IssueType("WRONG_ITEM_RECEIVED", "Wrong item received", "critical", "urgent",
              requires_customer_response=True, blocking=True),
    IssueType("OTHER", "Other", "medium", "normal"),
)

_BY_KEY: dict[str, IssueType] = {t.key: t for t in _TYPES}

# Legacy free-text types accepted before the enum (mapped so old rows/clients work).
_LEGACY_ALIASES: dict[str, str] = {
    "delay": "UNABLE_TO_MEET_TURNAROUND",
    "damage": "EXISTING_DAMAGE_DETECTED",
    "missing": "MISSING_ITEM",
    "alteration_price_change": "ALTERATION_NOT_STANDARD",
    "alteration_scope_change": "ALTERATION_NOT_STANDARD",
    "alteration_measurement_needed": "MEASUREMENT_REQUIRED",
    "alteration_not_possible": "ALTERATION_TECHNICIAN_REVIEW",
    "other": "OTHER",
}

KEYS: tuple[str, ...] = tuple(t.key for t in _TYPES)


def normalize_key(issue_type: str | None) -> str:
    raw = (issue_type or "").strip()
    if raw in _BY_KEY:
        return raw
    upper = raw.upper()
    if upper in _BY_KEY:
        return upper
    return _LEGACY_ALIASES.get(raw.lower(), "OTHER")


def resolve(issue_type: str | None) -> IssueType:
    """Return the canonical IssueType for any key/alias (OTHER as a safe default)."""
    return _BY_KEY[normalize_key(issue_type)]


def is_valid(issue_type: str | None) -> bool:
    return normalize_key(issue_type) in _BY_KEY


def catalogue() -> list[dict]:
    """UI-facing list of every issue type + its metadata."""
    return [
        {
            "key": t.key,
            "label": t.label,
            "severity": t.severity,
            "priority": t.priority,
            "requires_customer_response": t.requires_customer_response,
            "requires_photo": t.requires_photo,
            "requires_price_revision": t.requires_price_revision,
            "blocking": t.blocking,
        }
        for t in _TYPES
    ]
