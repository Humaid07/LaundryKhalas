"""Evolution API inbound webhook — real WhatsApp messages → Supabase inbox.

Point your Evolution instance's webhook at POST {backend}/webhooks/evolution
(event: messages.upsert). For each inbound customer message we:
  1. upsert the customer + conversation in Supabase (so it shows in the dashboard
     inbox),
  2. store the customer message,
  3. run the agent to DRAFT a reply and detect escalations,
  4. on an escalation/handoff -> mark the conversation Human Needed + create a
     flag (with the draft as the suggested reply). The draft is NEVER auto-sent
     unless EVOLUTION_AUTO_REPLY=true (default false) — honouring the MVP rule
     that live replies need human approval. Operator replies are sent live via
     the inbox human-message endpoint.

In local SQLite mode the webhook acknowledges but stores nothing (the inbox is a
Supabase feature) — it never fails webhook delivery.
"""
import structlog
from fastapi import APIRouter, Request

from agents.whatsapp_agent.agent import handle_message
from channels.evolution_whatsapp import EvolutionWhatsAppChannel, parse_evolution_webhook
from db import database
from db.repositories import conversations_repo, customers_repo, flags_repo, messages_repo
from services.escalation import detect_escalation
from settings import get_settings

router = APIRouter(prefix="/webhooks", tags=["evolution-webhook"])
logger = structlog.get_logger()

# Escalation category -> (flag_type, priority, team) for the dashboard inbox.
_ESCALATION_FLAG: dict[str, tuple[str, str, str]] = {
    "refund": ("refund_request", "urgent", "Customer Facing / Finance"),
    "payment_issue": ("payment_issue", "high", "Customer Facing / Finance"),
    "damaged_item": ("damaged_item", "high", "Customer Facing / Facility Facing"),
    "missing_item": ("missing_item", "high", "Customer Facing / Facility Facing"),
    "complaint": ("complaint", "medium", "Customer Facing"),
    "late_delivery": ("late_delivery", "high", "Customer Facing"),
    "b2b_quotation": ("b2b_lead", "medium", "Sales / Partner Acquisition"),
    "legal_safety": ("legal_safety", "urgent", "Customer Facing"),
    "angry": ("complaint", "high", "Customer Facing"),
}
_DEFAULT_FLAG = ("handoff", "high", "Customer Facing")


@router.post("/evolution")
async def receive_evolution_webhook(request: Request):
    settings = get_settings()
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - malformed body: ack without failing delivery
        return {"status": "ignored", "processed": 0}

    inbound = parse_evolution_webhook(payload)
    if not inbound:
        return {"status": "ignored", "processed": 0}

    # The inbox lives in Supabase. In local SQLite mode we acknowledge but don't
    # store (nothing to fail the webhook over).
    if not database.is_supabase_mode():
        return {
            "status": "ok",
            "stored": False,
            "processed": 0,
            "reason": "inbox requires DATABASE_MODE=supabase",
        }

    processed = 0
    for msg in inbound:
        customer = await customers_repo.get_or_create_by_phone(msg["phone"], msg["name"])
        convo = await conversations_repo.get_or_create_for_customer(
            customer["id"], external_id=f"evo:{msg['phone']}"
        )

        # 1) store the real inbound customer message + bump preview/unread
        await messages_repo.add_message(convo["id"], "customer", msg["text"], status="received")
        await conversations_repo.register_inbound(convo["id"], msg["text"])

        # 2) draft a reply (db=None -> pure text, no order side effects)
        reply = await handle_message(text=msg["text"], history=[], db=None)
        category = detect_escalation(msg["text"])
        handoff = bool(category) or reply.handoff

        if handoff:
            flag_type, priority, team = _ESCALATION_FLAG.get(category, _DEFAULT_FLAG)
            reason = (category or "handoff").replace("_", " ")
            await conversations_repo.set_flagged(
                convo["id"], reason=reason, priority=priority, team=team
            )
            await flags_repo.create(
                conversation_id=convo["id"],
                flag_type=flag_type,
                priority=priority,
                assigned_team=team,
                reason=f"Agent flagged: {reason}",
                suggested_reply=reply.text,
            )
        elif settings.evolution_auto_reply and settings.evolution_live_ready:
            # Explicitly opted-in auto-reply for the happy path only.
            try:
                await EvolutionWhatsAppChannel.from_settings().send_text(
                    to_phone=msg["phone"], text=reply.text
                )
                await messages_repo.add_message(
                    convo["id"], "agent", reply.text, status="sent"
                )
            except Exception as exc:  # noqa: BLE001 - never fail webhook on send error
                logger.warning("evolution_auto_reply_failed", error=str(exc))

        processed += 1

    return {"status": "ok", "stored": True, "processed": processed}
