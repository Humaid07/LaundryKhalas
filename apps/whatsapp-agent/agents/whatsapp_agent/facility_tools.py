"""Grounded facility tools for the agent + ops (read-only) and one audited write.

The read tools expose the CURRENT facility directory from the database (never a
hard-coded list, never the system prompt) so the agent's facility knowledge is
always live (task: "central database remains the source of truth"). Every output
is JSON-safe and PII/secret-free: internal rates and quality scores are NEVER
returned (privacy firewall §7), and the guidance tells the model not to reveal
internal operational detail to the customer.

``agent_update_facility_status`` is the ONLY facility mutation an agent may make —
open↔busy / pause / resume — and it goes through ``services.facility_admin`` so it
is validated + audited (actor/source/before/after) and invalidates the matching
cache. It is deliberately NOT registered in the customer tool schemas: a
customer-facing turn must not pause a facility (CLAUDE.md §6).
"""
from __future__ import annotations

import structlog

from db.repositories import catalogue_repo, facilities_repo, facility_settings_repo
from services import catalogue as cat_engine
from services import facility_admin, facility_matching

logger = structlog.get_logger(__name__)

_SAFE_NOTE = (
    "Never reveal internal rates, quality scores, or exact spare capacity to the "
    "customer. Use this only to confirm coverage/capability in your own words."
)


# --- Read tool schemas (Anthropic tool-use format; strict/closed objects) ---
READ_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "find_eligible_facilities",
        "description": (
            "Find Laundry Khalas facilities that can currently take a job for a "
            "service the customer named. Closed/paused facilities are excluded and "
            "busy ones rank below open ones. Use to confirm we can service a request "
            "— never quote internal rates or facility internals to the customer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service/category the customer wants."},
                "area": {"type": "string", "description": "Optional pickup area/neighbourhood."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_facilities",
        "description": (
            "List Laundry Khalas facilities (name, area, emirate, operating status, "
            "capacity). Optional status/emirate filters. Read-only, no internal rates "
            "or quality scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "open|busy|paused|closed"},
                "emirate": {"type": "string", "description": "Filter by emirate."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_facility",
        "description": "Get one facility's public profile by its id (no internal rates/quality).",
        "input_schema": {
            "type": "object",
            "properties": {"facility_id": {"type": "string"}},
            "required": ["facility_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_facility_services",
        "description": "List the service categories a facility accepts, by facility id.",
        "input_schema": {
            "type": "object",
            "properties": {"facility_id": {"type": "string"}},
            "required": ["facility_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_facility_operating_hours",
        "description": "Get a facility's weekly operating hours (structured, per weekday).",
        "input_schema": {
            "type": "object",
            "properties": {"facility_id": {"type": "string"}},
            "required": ["facility_id"],
            "additionalProperties": False,
        },
    },
]

READ_TOOL_NAMES = {s["name"] for s in READ_TOOL_SCHEMAS}


def _safe(d: dict) -> dict:
    """JSON-safe, customer-safe facility summary — NO quality_score, NO rates,
    NO raw timestamps."""
    return {
        "id": d.get("id"),
        "code": d.get("code"),
        "name": d.get("name"),
        "area": d.get("area"),
        "city": d.get("city"),
        "emirate": d.get("emirate"),
        "operating_status": d.get("operating_status"),
        "capacity_daily": d.get("capacity_daily"),
        "capacity_unit": d.get("capacity_unit"),
    }


async def _find_eligible(service: str | None, area: str | None) -> dict:
    code = cat_engine.resolve_category_alias(service) if service else None
    facs = await facility_matching.find_eligible(service_code=code)
    return {
        "count": len(facs),
        "available": bool(facs),
        "facilities": facs,  # already safe (from facility_matching._to_safe)
        "guidance": _SAFE_NOTE,
    }


async def _list_facilities(status: str | None, emirate: str | None) -> dict:
    rows = await facilities_repo.list_filtered(status=status, emirate=emirate)
    return {"count": len(rows), "facilities": [_safe(r) for r in rows], "guidance": _SAFE_NOTE}


async def _get_facility(facility_id: str) -> dict:
    prof = await facilities_repo.get(facility_id)  # partner-safe serializer
    if prof is None:
        return {"found": False, "guidance": "No facility with that id."}
    safe = _safe(prof)
    safe["full_address"] = prof.get("full_address")
    safe["service_radius_km"] = prof.get("service_radius_km")
    safe["accepts_orders"] = prof.get("accepts_orders")
    safe["services"] = await facilities_repo.get_services(facility_id)
    return {"found": True, "facility": safe, "guidance": _SAFE_NOTE}


async def _get_services(facility_id: str) -> dict:
    codes = await facilities_repo.get_services(facility_id)
    names = {c["code"]: c["name"] for c in await catalogue_repo.list_categories()}
    return {"services": [{"code": c, "name": names.get(c, c)} for c in codes]}


def _t(v) -> str | None:
    return None if v is None else str(v)


async def _get_hours(facility_id: str) -> dict:
    rows = await facility_settings_repo.list_timings(facility_id)
    return {
        "timings": [
            {
                "day_of_week": r.get("day_of_week"),
                "is_closed": bool(r.get("is_closed")),
                "is_24h": bool(r.get("is_24h")),
                "opens_at": _t(r.get("opens_at")),
                "closes_at": _t(r.get("closes_at")),
            }
            for r in rows
        ]
    }


async def dispatch(name: str, tool_input: dict) -> dict:
    """Run one facility READ tool. Raises ValueError for missing required input."""
    tool_input = tool_input or {}
    if name == "find_eligible_facilities":
        return await _find_eligible(
            (tool_input.get("service") or "").strip() or None,
            (tool_input.get("area") or "").strip() or None,
        )
    if name == "list_facilities":
        return await _list_facilities(
            (tool_input.get("status") or "").strip() or None,
            (tool_input.get("emirate") or "").strip() or None,
        )
    fid = (tool_input.get("facility_id") or "").strip()
    if not fid:
        raise ValueError("facility_id is required.")
    if name == "get_facility":
        return await _get_facility(fid)
    if name == "get_facility_services":
        return await _get_services(fid)
    if name == "get_facility_operating_hours":
        return await _get_hours(fid)
    raise ValueError(f"Unhandled facility tool '{name}'.")


# --- Audited write (NOT a customer tool) -----------------------------------
async def agent_update_facility_status(
    facility_id: str, status: str, *, actor_label: str = "whatsapp_agent"
) -> dict | None:
    """Agent/ops-initiated operational status change (open↔busy/pause/resume).
    Validated + audited via facility_admin; never touches rates or quality."""
    logger.info("agent_facility_status_change", facility_id=facility_id, status=status,
                actor=actor_label)
    return await facility_admin.change_status(
        facility_id, status, actor_id=None, actor_type="agent", source_app="whatsapp_agent"
    )
