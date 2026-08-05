"""Durable pending operational tasks (Supabase dev/test schema).

Each row makes a "let me check…" promise trackable: a due time + follow-up +
escalation rule. ``create`` computes due/follow-up from the per-type SLA
(``services/pending_tasks``) using DB-side ``now() + interval`` so timestamps are
authoritative. ``list_overdue`` powers a follow-up/escalation sweep.
"""
from __future__ import annotations

from db import database
from services import pending_tasks as tasks_svc

_COLS = (
    "id, task_ref, customer_id, conversation_id, order_id, complaint_id, quote_id, "
    "task_type, responsible_team, responsible_facility_id, status, due_at, "
    "follow_up_at, escalation_rule, escalated, customer_notification_status, "
    "notes, created_at, updated_at, resolved_at"
)


def _serialize(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "customer_id", "conversation_id", "order_id", "complaint_id",
              "responsible_facility_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


async def create(
    task_type: str,
    *,
    customer_id: str | None = None,
    conversation_id: str | None = None,
    order_id: str | None = None,
    complaint_id: str | None = None,
    quote_id: str | None = None,
    responsible_facility_id: str | None = None,
    notes: str | None = None,
) -> dict | None:
    """Insert a pending task with due/follow-up derived from the type SLA. Raises
    ValueError for an unknown task_type (caller must pass a valid AWAITING_* type)."""
    if not tasks_svc.is_valid_type(task_type):
        raise ValueError(f"Unknown pending task type: {task_type}")
    sla = tasks_svc.get_sla(task_type)
    due_hours = int(sla["due_hours"])
    follow_up_hours = int(sla["follow_up_hours"])
    team = sla["escalation_team"]
    escalation_rule = f"escalate to {team} if not actioned by due time"
    row = await database.fetchrow(
        f"""
        insert into pending_tasks
            (task_ref, customer_id, conversation_id, order_id, complaint_id, quote_id,
             task_type, responsible_team, responsible_facility_id, status,
             due_at, follow_up_at, escalation_rule, notes)
        values (
            'TSK-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
            $1, $2, $3, $4, $5, $6, $7, $8, 'open',
            now() + ($9 || ' hours')::interval,
            now() + ($10 || ' hours')::interval,
            $11, $12
        )
        returning {_COLS}
        """,
        customer_id, conversation_id, order_id, complaint_id, quote_id,
        task_type, team, responsible_facility_id,
        str(due_hours), str(follow_up_hours), escalation_rule, notes,
    )
    return _serialize(row)


async def facility_quote_status(order_uuid: str) -> str:
    """The §29 facility-quote status for one order, from its AWAITING_FACILITY_QUOTE task:
    pending | received | none. Best-effort read."""
    if not order_uuid:
        return "none"
    rows = await database.fetch(
        "select status from pending_tasks "
        "where order_id = $1::uuid and task_type = 'AWAITING_FACILITY_QUOTE'",
        order_uuid)
    if not rows:
        return "none"
    if any(r["status"] in ("open", "in_progress", "escalated") for r in rows):
        return "pending"
    return "received"


async def list_open(limit: int = 100) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from pending_tasks where status in ('open','in_progress') "
        f"order by due_at asc nulls last limit {max(1, min(int(limit), 200))}"
    )
    return [_serialize(r) for r in rows]


async def list_overdue(limit: int = 100) -> list[dict]:
    """Open tasks past their due time and not yet escalated — the escalation sweep."""
    rows = await database.fetch(
        f"select {_COLS} from pending_tasks "
        "where status in ('open','in_progress') and escalated = false "
        f"and due_at is not null and due_at < now() order by due_at asc "
        f"limit {max(1, min(int(limit), 200))}"
    )
    return [_serialize(r) for r in rows]


async def mark_done(task_id: str) -> dict | None:
    row = await database.fetchrow(
        f"update pending_tasks set status = 'done', resolved_at = now() "
        f"where id = $1 returning {_COLS}",
        task_id,
    )
    return _serialize(row)


async def mark_escalated(task_id: str) -> dict | None:
    row = await database.fetchrow(
        f"update pending_tasks set status = 'escalated', escalated = true "
        f"where id = $1 returning {_COLS}",
        task_id,
    )
    return _serialize(row)
