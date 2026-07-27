"""Facility order actions — the ONLY status transitions a facility may perform.

A facility drives the operational middle of an order (receive → clean → QC →
ready → hand to driver). It can NEVER cancel, refund, change price, mark an order
completed/delivered, or reassign it — those are platform/ops decisions (CLAUDE.md
§5/§6). ``apply_action`` validates ownership + the current status, updates the
order via a facility-SCOPED UPDATE, writes an ``order_events`` audit row
(actor_type='facility'), and returns the PII-safe facility order dict.
"""
from __future__ import annotations

from db import database
from db.repositories import facility_orders_repo, order_events_repo
from services import facility_notifications as facility_notify

# action -> {from: allowed current statuses, to: new status or None, event: audit type}.
# ``to=None`` records the action as an event WITHOUT changing status (accept / QC).
ALLOWED_ACTIONS: dict[str, dict] = {
    "accept": {"from": {"active", "pickup_scheduled"}, "to": None, "event": "facility_accepted"},
    "mark_received": {"from": {"active", "pickup_scheduled", "picked_up"}, "to": "picked_up",
                      "event": "received_at_facility"},
    "start_cleaning": {"from": {"picked_up"}, "to": "in_cleaning", "event": "cleaning_started"},
    "move_to_qc": {"from": {"in_cleaning"}, "to": None, "event": "quality_check"},
    "mark_ready": {"from": {"in_cleaning"}, "to": "ready_for_delivery", "event": "ready_for_delivery"},
    "confirm_handoff": {"from": {"ready_for_delivery"}, "to": "out_for_delivery",
                        "event": "handed_to_driver"},
}

# Actions a facility is explicitly NOT allowed to perform (router returns 403).
FORBIDDEN_ACTIONS = frozenset({
    "cancel", "refund", "change_price", "mark_completed", "mark_delivered",
    "complete", "reassign",
})


class ForbiddenFacilityAction(ValueError):
    """A facility attempted an action it is never permitted to perform."""


class InvalidFacilityAction(ValueError):
    """Unknown action, or the order's current status doesn't allow the action."""


async def apply_action(facility_id: str, order_id: str, action: str, *, actor_label: str) -> dict:
    """Validate + apply a facility action. Raises ``ForbiddenFacilityAction`` for
    a forbidden action, ``InvalidFacilityAction`` for an unknown action / illegal
    transition, and ``LookupError`` when the order isn't this facility's."""
    if action in FORBIDDEN_ACTIONS:
        raise ForbiddenFacilityAction(f"A facility cannot perform '{action}'.")
    spec = ALLOWED_ACTIONS.get(action)
    if spec is None:
        raise InvalidFacilityAction(f"Unknown action: {action}.")

    row = await facility_orders_repo.get_row(facility_id, order_id)
    if row is None:
        raise LookupError("Order not found for this facility.")

    current = row.get("status")
    if current not in spec["from"]:
        raise InvalidFacilityAction(
            f"'{action}' is not allowed from status '{current}'."
        )

    to_status = spec["to"]
    if to_status is not None and to_status != current:
        await database.fetchrow(
            "update orders set status = $2 where id = $1 and facility_id = $3 returning id",
            row["id"], to_status, facility_id,
        )

    await order_events_repo.create(
        order_uuid=row["id"],
        event_type=spec["event"],
        from_status=current,
        to_status=to_status,
        actor_type="facility",
        actor_name=actor_label,
        notes=f"Facility action '{action}' by {actor_label}.",
    )
    updated = await facility_orders_repo.get(facility_id, order_id)
    # Notify facility contacts of the status change (mock-first, never raises).
    if to_status is not None and to_status != current:
        await facility_notify.notify_order_status_updated(
            facility_id, {**(updated or {}), "id": row["id"]},
            old_status=current, new_status=to_status,
        )
    return updated or {}
