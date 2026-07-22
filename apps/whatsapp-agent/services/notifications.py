"""Customer WhatsApp notifications on operational order-status changes (spec §24).

Called AFTER a status change is committed. Never raises into the caller — a send
failure is logged as an order_event (NOTIFICATION_FAILED) and does not roll back a
valid status update. Idempotent: the same (order, status) is not notified twice.

Respects the agent operating mode + Evolution readiness, so it never messages a
real customer while paused, and in TEST mode only messages allow-listed numbers.
Only customer-facing statuses have a template; internal statuses send nothing.
"""
from __future__ import annotations

import structlog

from channels.evolution_whatsapp import EvolutionWhatsAppChannel
from db import database
from db.repositories import conversations_repo, messages_repo, order_events_repo
from services.privacy import mask_phone, normalize_e164
from settings import get_settings

logger = structlog.get_logger()

# Customer-facing status -> message template. Statuses NOT listed here (draft,
# active, support_required, …) are internal and send no customer notification.
_TEMPLATES: dict[str, str] = {
    "pickup_scheduled": "Your Laundry Khalaas order {oid} pickup is scheduled{when}. Our team will be there soon.",
    "picked_up": "Your Laundry Khalaas order {oid} has been picked up and is on its way to our facility.",
    "in_cleaning": "Your Laundry Khalaas order {oid} is now being cleaned with care.",
    "ready_for_delivery": "Good news! Your Laundry Khalaas order {oid} is ready and will be out for delivery soon.",
    "out_for_delivery": "Your Laundry Khalaas order {oid} is out for delivery.",
    "completed": "Your Laundry Khalaas order {oid} is complete. Thank you for choosing Laundry Khalaas!",
    "cancelled": "Your Laundry Khalaas order {oid} has been cancelled. Please contact us if you have any questions.",
}


def _sendable(phone_e164: str) -> tuple[bool, str]:
    s = get_settings()
    if not s.evolution_live_ready:
        return False, "evolution_not_live"
    mode = s.agent_operating_mode
    if mode == "paused":
        return False, "agent_paused"
    if mode == "test" and normalize_e164(phone_e164) not in s.allowed_auto_reply_numbers:
        return False, "test_mode_number_not_allowed"
    return True, "ok"


async def _already_notified(order_uuid: str, status: str) -> bool:
    return bool(await database.fetchval(
        "select 1 from order_events where order_id = $1 and event_type = 'NOTIFICATION_SENT' "
        "and to_status = $2 limit 1",
        order_uuid, status,
    ))


async def notify_status_change(order_read: dict, new_status: str) -> None:
    """Notify the customer of a status change. Safe/idempotent; never raises."""
    if new_status not in _TEMPLATES:
        return  # internal status — no customer notification
    order_uuid = order_read.get("id")
    conversation_id = order_read.get("conversation_id")
    order_id = order_read.get("order_id")
    if not (order_uuid and conversation_id):
        return

    try:
        if await _already_notified(order_uuid, new_status):
            logger.info("notification_skipped", order=order_id, reason="already_sent")
            return

        phone = await conversations_repo.get_customer_phone(conversation_id)
        if not phone:
            await order_events_repo.create(
                order_uuid=order_uuid, event_type="NOTIFICATION_FAILED", to_status=new_status,
                actor_type="system", notes="No customer phone on file.")
            return

        ok, reason = _sendable(phone)
        if not ok:
            await order_events_repo.create(
                order_uuid=order_uuid, event_type="NOTIFICATION_SKIPPED", to_status=new_status,
                actor_type="system", notes=f"Notification not sent: {reason}.")
            logger.info("notification_skipped", order=order_id, reason=reason,
                        sender=mask_phone(phone))
            return

        when = f" for {order_read['pickup_time']}" if order_read.get("pickup_time") else ""
        text = _TEMPLATES[new_status].format(oid=order_id, when=when)

        try:
            await EvolutionWhatsAppChannel.from_settings().send_text(to_phone=phone, text=text)
        except Exception as exc:  # noqa: BLE001 - a send failure must not roll back the status
            await order_events_repo.create(
                order_uuid=order_uuid, event_type="NOTIFICATION_FAILED", to_status=new_status,
                actor_type="system", notes=f"WhatsApp send failed: {type(exc).__name__}.")
            logger.warning("notification_failed", order=order_id, error=str(exc))
            return

        await messages_repo.add_message(
            conversation_id, "agent", text, status="sent",
            metadata={"notification": True, "status": new_status})
        await order_events_repo.create(
            order_uuid=order_uuid, event_type="NOTIFICATION_SENT", to_status=new_status,
            actor_type="system", notes=f"Customer notified: {new_status}.")
        logger.info("notification_sent", order=order_id, status=new_status, sender=mask_phone(phone))
    except Exception as exc:  # noqa: BLE001 - notifications never break the status update
        logger.warning("notification_error", order=order_id, error=str(exc))
