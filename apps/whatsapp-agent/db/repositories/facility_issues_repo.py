"""Facility-raised issue reads/writes against the dev/test Supabase schema.

Facilities raise operational issues to the internal LaundryKhalas team; each has
a threaded conversation (facility_issue_messages). Mirrors the tickets pattern.
Privacy: issues carry area/city + order business-id only, never customer PII.

Every FACILITY-side call passes ``facility_id`` so the query is scoped; the
INTERNAL inbox passes ``facility_id=None`` to list across all facilities.
"""
from __future__ import annotations

from db import database

# Columns shared by every issue read (kept in sync with mig 000018 + 000047).
_ISSUE_COLS = (
    "i.id, i.facility_id, i.order_id, i.order_ref, i.conversation_id, "
    "i.issue_type, i.title, i.message, i.severity, i.priority, "
    "i.assigned_team, i.assigned_internal_owner, i.status, i.requested_help, "
    "i.order_item_id, i.requires_customer_response, i.requires_photo, "
    "i.requires_price_revision, i.photo_ids, "
    "i.created_by_user_id, i.created_by_label, i.created_at, i.updated_at, i.resolved_at"
)
# RETURNING clause for writes (no facility join / alias).
_RETURNING = _ISSUE_COLS.replace("i.", "")

_SELECT = f"""
  select {_ISSUE_COLS}
    from facility_issues i
"""

_SELECT_WITH_FACILITY = f"""
  select {_ISSUE_COLS}, f.name as facility_name, f.code as facility_code
    from facility_issues i
    left join facilities f on f.id = i.facility_id
"""


async def create(
    *,
    facility_id: str,
    issue_type: str,
    message: str,
    title: str | None = None,
    severity: str = "medium",
    priority: str = "normal",
    order_uuid: str | None = None,
    order_ref: str | None = None,
    order_item_id: str | None = None,
    requires_customer_response: bool = False,
    requires_photo: bool = False,
    requires_price_revision: bool = False,
    photo_ids: list[str] | None = None,
    created_by_user_id: str | None = None,
    created_by_label: str | None = None,
    requested_help: str | None = None,
) -> dict | None:
    import json

    return await database.fetchrow(
        f"""
        insert into facility_issues
            (facility_id, order_id, order_ref, issue_type, title, message,
             severity, priority, status, requested_help, created_by_user_id,
             created_by_label, order_item_id, requires_customer_response,
             requires_photo, requires_price_revision, photo_ids,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8, 'open', $9, $10, $11,
                $12, $13, $14, $15, $16::jsonb,
                true, false, 'dev', false)
        returning {_RETURNING}
        """,
        facility_id, order_uuid, order_ref, issue_type, title, message,
        severity, priority, requested_help, created_by_user_id, created_by_label,
        order_item_id, requires_customer_response, requires_photo,
        requires_price_revision, json.dumps(photo_ids or []),
    )


async def has_blocking_open_issue(order_uuid: str) -> bool:
    """True when the order has an OPEN issue that must be resolved before it can
    advance toward delivery (mark ready / handoff) — the operational "pause"."""
    if not order_uuid:
        return False
    val = await database.fetchval(
        "select exists (select 1 from facility_issues "
        "where order_id = $1::uuid and status not in ('resolved','closed') "
        "and (requires_price_revision or requires_customer_response))",
        order_uuid,
    )
    return bool(val)


async def status_for_order(order_uuid: str) -> str:
    """The §29 facility-issue status for one order: open | resolved | none. Best-effort."""
    if not order_uuid:
        return "none"
    rows = await database.fetch(
        "select status from facility_issues where order_id = $1::uuid", order_uuid)
    if not rows:
        return "none"
    return "open" if any(r["status"] != "resolved" for r in rows) else "resolved"


async def list_issues(facility_id: str | None = None, status: str | None = None) -> list[dict]:
    conds: list[str] = []
    params: list = []
    if facility_id is not None:
        params.append(facility_id)
        conds.append(f"i.facility_id = ${len(params)}")
    if status:
        params.append(status)
        conds.append(f"i.status = ${len(params)}")
    where = (" where " + " and ".join(conds)) if conds else ""
    return await database.fetch(
        _SELECT_WITH_FACILITY + where + " order by i.created_at desc", *params
    )


async def get(issue_id: str, facility_id: str | None = None) -> dict | None:
    params: list = [issue_id]
    cond = "i.id = $1"
    if facility_id is not None:
        params.append(facility_id)
        cond += f" and i.facility_id = ${len(params)}"
    return await database.fetchrow(
        _SELECT_WITH_FACILITY + f" where {cond}", *params
    )


async def set_status(
    issue_id: str, status: str, *, assigned_internal_owner: str | None = None
) -> dict | None:
    resolved = ", resolved_at = now()" if status in ("resolved", "closed") else ""
    return await database.fetchrow(
        f"""
        update facility_issues
           set status = $2,
               assigned_internal_owner = coalesce($3, assigned_internal_owner){resolved}
         where id = $1
        returning {_RETURNING}
        """,
        issue_id, status, assigned_internal_owner,
    )


async def resolve(issue_id: str) -> dict | None:
    return await set_status(issue_id, "resolved")
