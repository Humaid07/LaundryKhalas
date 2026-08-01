"""Guard: the customer-facing WhatsApp agent must never reach bank details or
internal ratings/notes (spec §13, CLAUDE.md §7).

These lock in that:
  * the agent's facility tool output and the customer-safe matching dict expose
    no banking, rating, quality-score, or internal-note fields;
  * the agent package does not import the bank / ratings service modules at all.
"""
import re
from pathlib import Path

from agents.whatsapp_agent import facility_tools
from services import facility_matching

# Sensitive tokens matched as whole underscore-delimited words in a key, so
# "operating_status" does NOT trip on "rating" and "capacity" not on "pay".
_FORBIDDEN = {"iban", "account", "bank", "swift", "notes", "internal",
              "overall", "evaluation", "rating", "weight", "quality",
              "payout", "rate", "score"}

_AGENT_DIR = Path(facility_tools.__file__).resolve().parent


def _assert_clean(d: dict):
    for key in d:
        tokens = set(re.split(r"[^a-z0-9]+", key.lower()))
        leaked = tokens & _FORBIDDEN
        assert not leaked, f"agent-facing dict leaked {leaked} via key '{key}'"


def test_agent_facility_tool_dict_has_no_sensitive_fields():
    row = {
        "id": "fac-1", "code": "FAC-1", "name": "Marina", "area": "Marina",
        "city": "Dubai", "emirate": "Dubai", "operating_status": "open",
        "quality_score": 88.5, "payout_rate": 12.5,  # internal — must be dropped
    }
    _assert_clean(facility_tools._safe(row))


def test_customer_safe_matching_dict_has_no_sensitive_fields():
    fac = {
        "id": "fac-1", "code": "FAC-1", "name": "Marina", "area": "Marina",
        "city": "Dubai", "emirate": "Dubai", "operating_status": "open",
        "capacity_daily": 100, "capacity_unit": "orders_per_day",
        "quality_score": 88.5, "active_load": 3,
    }
    _assert_clean(facility_matching._to_safe(fac, None))


def test_agent_package_does_not_import_bank_or_ratings():
    offenders = []
    for path in _AGENT_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for mod in ("facility_bank", "rating_service", "facility_bank_repo",
                    "facility_evaluations_repo", "driver_evaluations_repo"):
            if mod in text:
                offenders.append(f"{path.name} references {mod}")
    assert not offenders, offenders
