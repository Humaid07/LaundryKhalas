"""Facility notifications — mock-first + env-gated (mirrors services/notifications.py).

When a new order is assigned to a facility (and for SLA risk, issue replies, etc.)
we notify the facility's registered contacts. By DEFAULT (FACILITY_NOTIFICATIONS_
MODE=mock) or whenever no live channel is ready, this only LOGS a
``facility_notifications`` row (status='mock_logged', channel='mock') and never
sends externally. Only when a live channel is ready would it actually send.

Idempotent: the same (order, type) is not logged twice. Never raises into the
caller. Notifications carry NO full customer phone/address (privacy firewall).
"""
from __future__ import annotations

import structlog

from db.repositories import facility_notifications_repo
from settings import get_settings

logger = structlog.get_logger()


def _live_ready() -> bool:
    s = get_settings()
    return s.facility_notifications_mode_normalized != "mock" and s.facility_notifications_ready


def _new_order_preview(order_read: dict) -> str:
    """Message preview WITHOUT customer full phone/address (privacy firewall)."""
    order_ref = order_read.get("order_id") or "your new order"
    service = order_read.get("service") or "Laundry"
    area = order_read.get("area") or order_read.get("city") or ""
    area_part = f"{area}. " if area else ""
    return (
        f"New LaundryKhalas order assigned: {order_ref}. Service: {service}. "
        f"{area_part}Open Facility Dashboard for details."
    )


# Friendly labels for the common facility-visible order statuses (message text).
_STATUS_LABELS: dict[str, str] = {
    "picked_up": "Received at facility",
    "in_cleaning": "In cleaning",
    "ready_for_delivery": "Ready for delivery",
    "out_for_delivery": "Handed to driver",
    "completed": "Completed",
    "cancellation_requested": "Cancellation requested",
    "support_required": "On hold — needs attention",
}


def _status_label(status: str | None) -> str:
    if not status:
        return "Updated"
    return _STATUS_LABELS.get(status, str(status).replace("_", " ").capitalize())


def _order_ref(order_read: dict) -> str:
    return order_read.get("order_id") or "your order"


def _status_preview(order_read: dict, new_status: str) -> str:
    """PII-safe status-update preview (order ref + status + SLA text only)."""
    sla = order_read.get("turnaround_text") or order_read.get("estimated_delivery_text")
    sla_part = f" SLA: {sla}." if sla else ""
    return f"Order {_order_ref(order_read)} updated: {_status_label(new_status)}.{sla_part}"


def _driver_preview(order_read: dict, task_type: str, expected) -> str:
    """PII-safe driver-assigned preview (driver contact/customer data excluded)."""
    task = (task_type or "handoff").replace("_", " ")
    exp = f" Expected completion: {expected}." if expected else ""
    return f"Driver assigned for order {_order_ref(order_read)}. Task: {task}.{exp}"


def _issue_reply_preview(issue: dict) -> str:
    """PII-safe issue-reply preview — internal notes are never included."""
    order_ref = issue.get("order_ref")
    ref_part = f" for order {order_ref}" if order_ref else ""
    return (f"LaundryKhalas Operations replied on your facility issue{ref_part}. "
            "Open Facility Dashboard to view the reply.")


async def notify_new_order_assigned(facility_id: str, order_read: dict) -> dict | None:
    """Idempotent per (order, 'new_order_assigned'). Logs a mock row unless a live
    channel is ready. Never raises."""
    return await notify(
        facility_id,
        "new_order_assigned",
        order_uuid=order_read.get("id") or order_read.get("order_uuid"),
        order_ref=order_read.get("order_id"),
        message_preview=_new_order_preview(order_read),
    )


async def notify_order_status_updated(
    facility_id: str, order_read: dict, *, old_status: str | None = None, new_status: str,
) -> dict | None:
    """Notify facility contacts of an order status change. Idempotent per
    (order, new_status) via a dedupe key. Never raises."""
    order_uuid = order_read.get("id") or order_read.get("order_uuid")
    key_base = order_uuid or order_read.get("order_id")
    return await notify(
        facility_id, "order_status_updated",
        order_uuid=order_uuid, order_ref=order_read.get("order_id"),
        message_preview=_status_preview(order_read, new_status),
        dedupe_key=f"{key_base}:status:{new_status}",
    )


async def notify_driver_assigned(
    facility_id: str, order_read: dict, *, task_type: str = "facility_handoff",
    expected_completion=None, driver_id: str | None = None,
) -> dict | None:
    """Notify facility contacts that a driver was assigned to an order task.
    Idempotent per (order, driver, task) via a dedupe key. Never raises."""
    order_uuid = order_read.get("id") or order_read.get("order_uuid")
    key_base = order_uuid or order_read.get("order_id")
    return await notify(
        facility_id, "driver_assigned",
        order_uuid=order_uuid, order_ref=order_read.get("order_id"),
        message_preview=_driver_preview(order_read, task_type, expected_completion),
        dedupe_key=f"{key_base}:driver:{driver_id}:{task_type}",
    )


async def notify_internal_issue_reply(
    facility_id: str, issue: dict, *, message_id: str | None = None,
) -> dict | None:
    """Notify facility contacts that Operations replied on a facility issue.
    Idempotent per (issue, message) via a dedupe key. Never raises."""
    issue_uuid = issue.get("id")
    return await notify(
        facility_id, "internal_issue_reply",
        issue_uuid=issue_uuid, order_ref=issue.get("order_ref"),
        message_preview=_issue_reply_preview(issue),
        dedupe_key=f"issue:{issue_uuid}:reply:{message_id}",
    )


async def notify(
    facility_id: str,
    type: str,
    *,
    order_uuid: str | None = None,
    order_ref: str | None = None,
    issue_uuid: str | None = None,
    message_preview: str | None = None,
    destination_masked: str | None = None,
    dedupe_key: str | None = None,
) -> dict | None:
    """General facility-notification helper. Mock-logs by default; only sends when
    a LIVE channel is ready. Idempotent per ``dedupe_key`` (preferred) or per
    (order, type). Never raises."""
    try:
        if dedupe_key:
            if await facility_notifications_repo.exists_by_dedupe(facility_id, dedupe_key):
                logger.info("facility_notification_skipped", facility=facility_id,
                            type=type, reason="already_logged")
                return None
        elif order_uuid and await facility_notifications_repo.exists_for_order(
            facility_id, order_uuid, type
        ):
            logger.info("facility_notification_skipped", facility=facility_id,
                        type=type, reason="already_logged")
            return None

        if not _live_ready():
            # Mock mode (or no live channel) — LOG ONLY, never send externally.
            return await facility_notifications_repo.create(
                facility_id=facility_id, type=type, order_uuid=order_uuid,
                order_ref=order_ref, issue_uuid=issue_uuid, channel="mock",
                status="mock_logged", destination_masked=destination_masked,
                message_preview=message_preview, dedupe_key=dedupe_key,
            )

        # A live channel is ready. (No live facility channel is wired yet — this
        # branch records the intent as 'pending'; the actual send is added when a
        # provider is approved. We still never raise.)
        return await facility_notifications_repo.create(
            facility_id=facility_id, type=type, order_uuid=order_uuid,
            order_ref=order_ref, issue_uuid=issue_uuid,
            channel=get_settings().facility_notifications_mode_normalized,
            status="pending", destination_masked=destination_masked,
            message_preview=message_preview, dedupe_key=dedupe_key,
        )
    except Exception as exc:  # noqa: BLE001 - notifications never break the caller
        logger.warning("facility_notification_error", facility=facility_id,
                       type=type, error=str(exc))
        return None
