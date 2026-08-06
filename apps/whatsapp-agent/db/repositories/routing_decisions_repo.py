"""Routing-decision snapshot persistence (asyncpg / Supabase).

One row per routing evaluation (production OR test OR simulator): the full candidate
breakdown, the selection, and — in shadow mode — the legacy-vs-advanced comparison.
Diagnostics are internal-only (RLS-denied); never shown to customers or facilities.
"""
from __future__ import annotations

import json

from db import database

_COLS = (
    "id, order_id, order_ref, environment, routing_mode, routing_version, simulation_time, "
    "customer_area, customer_latitude, customer_longitude, requested_service, service_subtype, "
    "required_capabilities, requested_priority, requested_pickup_at, required_turnaround_hours, "
    "candidates, eligible_count, rejected_count, score_components, selected_facility_id, "
    "selected_driver_id, selected_pickup_slot_id, selection_reason, legacy_selected_facility_id, "
    "advanced_selected_facility_id, selections_matched, fallback_used, created_by, created_at"
)


def to_read(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "order_id", "selected_facility_id", "selected_driver_id",
              "legacy_selected_facility_id", "advanced_selected_facility_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("candidates", "score_components"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (ValueError, TypeError):
                pass
    return d


async def create(
    *,
    order_uuid: str | None,
    order_ref: str | None,
    environment: str,
    routing_mode: str,
    routing_version: str,
    result: dict,
    request: dict,
    simulation_time=None,
    legacy_selected_facility_id: str | None = None,
    advanced_selected_facility_id: str | None = None,
    selections_matched: bool | None = None,
    fallback_used: bool = False,
    created_by: str | None = None,
    is_test_data: bool = False,
) -> dict | None:
    candidates = (result.get("eligible_candidates") or []) + (result.get("rejected_candidates") or [])
    row = await database.fetchrow(
        f"""
        insert into routing_decisions
            (order_id, order_ref, environment, routing_mode, routing_version, simulation_time,
             customer_area, customer_latitude, customer_longitude, requested_service, service_subtype,
             required_capabilities, requested_priority, requested_pickup_at, required_turnaround_hours,
             candidates, eligible_count, rejected_count, score_components, selected_facility_id,
             selected_driver_id, selected_pickup_slot_id, selection_reason, legacy_selected_facility_id,
             advanced_selected_facility_id, selections_matched, fallback_used, created_by, is_test_data)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::text[],$13,$14,$15,$16::jsonb,$17,$18,
                $19::jsonb,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29)
        returning {_COLS}
        """,
        order_uuid, order_ref, environment, routing_mode, routing_version, simulation_time,
        request.get("area"), request.get("lat"), request.get("lon"),
        request.get("service_code"), request.get("service_subtype"),
        list(request.get("required_capabilities") or []), request.get("priority"),
        request.get("pickup_at"), request.get("required_turnaround_hours"),
        json.dumps(candidates), result.get("eligible_count", 0), result.get("rejected_count", 0),
        json.dumps(result.get("score_components")), result.get("selected_facility_id"),
        result.get("selected_driver_id"), result.get("selected_pickup_slot_id"),
        result.get("selection_reason"), legacy_selected_facility_id, advanced_selected_facility_id,
        selections_matched, fallback_used, created_by, is_test_data,
    )
    return to_read(row)


async def list_recent(*, environment: str | None = None, limit: int = 50) -> list[dict]:
    if environment:
        rows = await database.fetch(
            f"select {_COLS} from routing_decisions where environment = $1 "
            "order by created_at desc limit $2", environment, limit)
    else:
        rows = await database.fetch(
            f"select {_COLS} from routing_decisions order by created_at desc limit $1", limit)
    return [to_read(r) for r in rows]


async def list_mismatches(*, limit: int = 50) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from routing_decisions where selections_matched = false "
        "order by created_at desc limit $1", limit)
    return [to_read(r) for r in rows]
