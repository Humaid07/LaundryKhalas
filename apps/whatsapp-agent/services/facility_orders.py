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
from db.repositories import (
    facility_issues_repo,
    facility_order_reviews_repo,
    facility_orders_repo,
    order_events_repo,
    order_notes_repo,
    order_photos_repo,
)
from services import facility_notifications as facility_notify
from services import facility_order_view as order_view_svc

# Actions that may not proceed until the facility has acknowledged an up-to-date
# review of the order details, notes and photos (spec: "Start Processing" gate).
_REVIEW_GATED_ACTIONS = frozenset({"start_cleaning"})

# Actions that advance the order toward delivery — blocked while a blocking issue
# (price revision / customer response required) is open, so an order is never
# shipped with an unresolved clarification (spec: "pause the affected stage").
_ISSUE_GATED_ACTIONS = frozenset({"mark_ready", "confirm_handoff"})

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


class ReviewNotAcknowledged(ValueError):
    """A processing action was attempted before the facility acknowledged an
    up-to-date review of the order details, notes and photos."""


class ProcessingBlocked(ValueError):
    """An order cannot advance toward delivery because a blocking issue (price
    revision / customer response required) is still open."""


async def _review_is_current(facility_id: str, order_uuid: str) -> bool:
    """True when a live acknowledgement matches the order's current version
    signals. Fail-closed: any error resolving the review blocks processing so the
    facility never starts work on unreviewed details."""
    notes_all = await order_notes_repo.list_all(order_uuid)
    photo_count = len(await order_photos_repo.list_for_order(order_uuid))
    versions = order_view_svc.compute_versions(notes_all=notes_all, photo_count=photo_count)
    review = await facility_order_reviews_repo.latest_for_order(facility_id, order_uuid)
    return bool(order_view_svc.build_review_ack(review, versions).get("up_to_date"))


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

    # Review gate: a facility cannot START PROCESSING until it has acknowledged an
    # up-to-date review of the order details, notes and photos (backend-enforced,
    # never trusting the client). Runs only after the status check so an illegal
    # transition still fails first.
    if action in _REVIEW_GATED_ACTIONS and not await _review_is_current(facility_id, str(row["id"])):
        raise ReviewNotAcknowledged(
            "Acknowledge the order details, notes and photos before processing."
        )

    # Issue gate: don't let an order advance to ready/handoff while a blocking
    # issue (needs a price revision or a customer response) is still open.
    if action in _ISSUE_GATED_ACTIONS and await facility_issues_repo.has_blocking_open_issue(str(row["id"])):
        raise ProcessingBlocked(
            "Resolve the open issue (customer response / price revision) before this step."
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
