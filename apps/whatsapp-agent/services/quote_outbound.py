"""Proactive outbound push of a facility-confirmed price to the customer.

When a facility quote reaches ``customer_pending`` (Operations approved the price),
this sends the short, grounded relay message to the customer on WhatsApp — reusing
the SAME outbound gate as the follow-up sweeper (never when paused; in test mode
only to the allow-list; live otherwise). The message is composed by the backend
(never invented by the LLM). Sending is claimed atomically so a retry / concurrent
worker never double-sends; if the send can't happen now, the agent's
``get_pending_facility_quote`` relay tool still surfaces the price when the customer
next messages.
"""
from __future__ import annotations

import structlog

from channels.evolution_whatsapp import EvolutionWhatsAppChannel
from db import database
from db.repositories import conversations_repo, facility_quote_revisions_repo, order_events_repo
from services import facility_quote_workflow
from services.privacy import mask_phone, normalize_e164
from settings import get_settings

logger = structlog.get_logger()


def _may_send(phone: str | None) -> bool:
    """The webhook/follow-up outbound gate: never when replies are disabled; in test
    mode only to the allow-list; otherwise (live) allowed."""
    s = get_settings()
    if not getattr(s, "agent_replies_enabled", False):
        return False
    if getattr(s, "agent_operating_mode", "test") == "test":
        return normalize_e164(phone or "") in getattr(s, "allowed_auto_reply_numbers", set())
    return True


async def send_customer_quote(order_uuid: str, *, order_ref: str | None = None) -> dict:
    """Push the pending facility-confirmed price for an order to the customer.
    Returns ``{sent, reason?}``. Never raises."""
    try:
        if not database.is_supabase_mode():
            return {"sent": False, "reason": "not_supabase_mode"}
        pending = await facility_quote_workflow.get_pending_quote_for_order(order_uuid)
        if not pending:
            return {"sent": False, "reason": "no_pending_quote"}

        # Atomic claim — only the caller that flips SENT_TO_CUSTOMER proceeds.
        claimed = await facility_quote_revisions_repo.mark_sent_to_customer(pending["revision_id"])
        if claimed is None:
            return {"sent": False, "reason": "already_sent"}

        conversation_id = await database.fetchval(
            "select conversation_id from orders where id = $1::uuid", order_uuid)
        if not conversation_id:
            return {"sent": False, "reason": "no_conversation"}
        phone = await conversations_repo.get_customer_phone(str(conversation_id))
        if not phone:
            return {"sent": False, "reason": "no_phone"}
        if not _may_send(phone):
            # Not sendable now (paused / not allow-listed). The price is still
            # relayed by the agent tool when the customer next messages.
            return {"sent": False, "reason": "outbound_gated"}

        await EvolutionWhatsAppChannel.from_settings().send_text(
            to_phone=phone, text=pending["relay_text"])
        await order_events_repo.create(
            order_uuid=order_uuid, event_type="customer_quote_sent",
            actor_type="system", actor_name="Quote Relay",
            notes="Facility-confirmed price sent to the customer.",
            metadata={"revision_id": pending["revision_id"], "quote_version": pending["quote_version"]})
        logger.info("customer_quote_sent", order=order_ref or order_uuid,
                    to=mask_phone(phone), price=pending["final_price"])
        return {"sent": True, "final_price": pending["final_price"], "currency": pending["currency"]}
    except Exception as exc:  # noqa: BLE001 — an outbound push must never break the caller
        logger.warning("customer_quote_send_failed", order=order_ref or order_uuid, error=str(exc))
        return {"sent": False, "reason": "error"}
