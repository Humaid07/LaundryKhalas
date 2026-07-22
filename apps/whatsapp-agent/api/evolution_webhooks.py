"""Evolution API inbound webhook — real WhatsApp messages → Supabase.

Point your Evolution instance's webhook at POST {backend}/webhooks/evolution
(event: messages.upsert). For each inbound customer message (from an APPROVED
test number only) we:
  1. upsert the customer + conversation in Supabase (dashboard inbox),
  2. EXTRACT structured customer/order details from the whole conversation so far
     and backfill the customer profile (name/city/area/address/language),
  3. store the customer message (with derived intent/domain/decision metadata),
  4. on a booking: create/update the conversation's DRAFT order + write
     order_events; promote it to pickup_scheduled/active only once the customer
     confirms and enough detail exists,
  5. on an escalation/handoff (refund/complaint/damage/…): raise a flag + ticket,
     mark the conversation Human Needed, and NEVER auto-resolve or auto-send,
  6. auto-reply live via Evolution only when EVOLUTION_AUTO_REPLY=true AND the
     decision layer approved it AND the sender is approved.

Safety: a non-approved sender is dropped before anything is stored (no store, no
agent, no send). In local SQLite mode the webhook acknowledges but stores nothing
(the rich model lives in Supabase) — it never fails webhook delivery. No raw
phone / address is ever logged.
"""
import structlog
from fastapi import APIRouter, Request

from agents.whatsapp_agent.agent import handle_message
from channels.evolution_whatsapp import EvolutionWhatsAppChannel, parse_evolution_webhook
from db import database
from db.repositories import (
    conversations_repo,
    customers_repo,
    flags_repo,
    messages_repo,
    order_events_repo,
    orders_repo,
    tickets_repo,
)
from services.auto_reply import SENDER_NOT_ALLOWED, should_auto_reply
from services.escalation import detect_escalation
from services.order_extraction import accumulate_from_messages
from services.privacy import mask_phone, normalize_e164
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


def _confirmation_reply(order_row: dict) -> str:
    """Deterministic confirmation message for a just-confirmed booking. No
    invented figures — the amount, if shown, is the configured per-item estimate
    and is explicitly flagged as team-confirmed."""
    oid = order_row["order_id"]
    service = order_row.get("service") or "your order"
    lines = ["✅ Thank you! Your booking is confirmed.", f"Order {oid} — {service}."]
    if order_row.get("pickup_slot"):
        lines.append(f"Pickup: {order_row['pickup_slot']}.")
    if order_row.get("amount") is not None:
        lines.append(
            f"Estimated total: {order_row['amount']} AED "
            "(our team will confirm the final price)."
        )
    lines.append("Our team will reach out shortly to finalise the details.")
    return "\n".join(lines)


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

    # The rich model lives in Supabase. In local SQLite mode we acknowledge but
    # don't store (nothing to fail the webhook over).
    if not database.is_supabase_mode():
        return {
            "status": "ok",
            "stored": False,
            "processed": 0,
            "reason": "capture requires DATABASE_MODE=supabase",
        }

    # SAFETY: only approved test numbers (EVOLUTION_ALLOWED_TEST_NUMBERS) are ever
    # processed or replied to. Empty list = no one is processed (fail safe).
    allowed = settings.allowed_auto_reply_numbers

    processed = 0
    skipped = 0
    for msg in inbound:
        sender = normalize_e164(msg["phone"])
        masked = mask_phone(sender)

        # --- Sender allow-list gate (before storing / calling the agent) -------
        if sender not in allowed:
            skipped += 1
            logger.info(
                "evolution_inbound_skipped",
                sender=masked,
                allowed_sender=False,
                auto_reply_decision="hold",
                no_auto_reply_reason=SENDER_NOT_ALLOWED,
            )
            continue

        customer = await customers_repo.get_or_create_by_phone(msg["phone"], msg["name"])
        convo = await conversations_repo.get_or_create_for_customer(
            customer["id"], external_id=f"evo:{msg['phone']}"
        )

        # 1) Conversation context BEFORE this message: prior turns (for the
        #    agent), whether we've already welcomed (welcome-once), and every
        #    prior CUSTOMER message (so extraction accumulates across the whole
        #    conversation, not just this line).
        prior = await messages_repo.list_messages(convo["id"])
        history = [
            (m["sender_type"], m["message_text"])
            for m in prior
            if m["sender_type"] in ("customer", "agent")
        ]
        welcome_sent = any(m["sender_type"] == "agent" for m in prior)
        customer_texts = [m["message_text"] for m in prior if m["sender_type"] == "customer"]
        customer_texts.append(msg["text"])

        # 2) Extract structured details across the whole conversation + decide.
        details = accumulate_from_messages(customer_texts)
        decision = should_auto_reply(msg["text"], {"welcome_sent": welcome_sent})
        category = detect_escalation(msg["text"])
        is_escalation = decision.domain == "escalation" or bool(category)
        will_send = bool(
            decision.send_reply
            and settings.evolution_auto_reply
            and settings.evolution_live_ready
            and not is_escalation
        )

        # 3) Store the inbound message with derived (non-PII) metadata.
        inbound_msg = await messages_repo.add_message(
            convo["id"],
            "customer",
            msg["text"],
            status="received",
            metadata={
                "intent": decision.intent,
                "domain": decision.domain,
                "auto_reply_decision": "send" if will_send else "hold",
                "escalation": category,
            },
        )
        await conversations_repo.register_inbound(convo["id"], msg["text"])

        # 4) Backfill the customer profile from what we've learned. Address is
        #    stored backend-only and is NOT logged.
        cust_fields = details.customer_fields()
        if cust_fields:
            await customers_repo.update_customer_details(customer["id"], cust_fields)

        # --- ESCALATION: flag + ticket, mark human-needed, never auto-resolve ---
        if is_escalation:
            reply = await handle_message(text=msg["text"], history=history, db=None)
            flag_type, priority, team = _ESCALATION_FLAG.get(category, _DEFAULT_FLAG)
            reason = (category or "handoff").replace("_", " ")
            open_order = await orders_repo.get_open_for_conversation(convo["id"])
            order_uuid = open_order["id"] if open_order else None

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
                order_id=order_uuid,
            )
            await tickets_repo.create_or_update(
                conversation_id=convo["id"],
                ticket_type=flag_type,
                priority=priority,
                assigned_team=team,
                title=f"{reason.title()} — WhatsApp",
                description=f"Raised from WhatsApp conversation. Category: {reason}.",
                order_uuid=order_uuid,
            )
            if order_uuid:
                await order_events_repo.create(
                    order_uuid=order_uuid,
                    event_type="human_handoff_created",
                    actor_type="agent",
                    notes=f"Escalation raised: {reason}.",
                )
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "human_needed")
            logger.info(
                "evolution_inbound_escalation",
                sender=masked,
                allowed_sender=True,
                auto_reply_decision="hold",
                flag_type=flag_type,
                order_linked=bool(order_uuid),
            )
            processed += 1
            continue

        # --- HAPPY PATH: create/update the draft order from the conversation ----
        order_result = None
        if details.has_booking_details():
            order_result = await orders_repo.create_or_update_draft_from_conversation(
                conversation_id=convo["id"], customer=customer, details=details
            )

        # 5) Auto-reply (only if opted in + approved by the decision layer).
        if will_send:
            if order_result and order_result["confirmed_now"]:
                reply_text = _confirmation_reply(order_result["row"])
            else:
                reply = await handle_message(text=msg["text"], history=history, db=None)
                reply_text = reply.text
            try:
                await EvolutionWhatsAppChannel.from_settings().send_text(
                    to_phone=msg["phone"], text=reply_text
                )
                await messages_repo.add_message(
                    convo["id"],
                    "agent",
                    reply_text,
                    status="sent",
                    metadata={
                        "intent": decision.intent,
                        "domain": decision.domain,
                        "auto_reply_decision": "send",
                    },
                )
                logger.info(
                    "evolution_auto_reply_sent",
                    sender=masked,
                    allowed_sender=True,
                    order_confirmed=bool(order_result and order_result["confirmed_now"]),
                )
            except Exception as exc:  # noqa: BLE001 - never fail webhook on send error
                logger.warning("evolution_auto_reply_failed", sender=masked, error=str(exc))
        else:
            # Stored (and any draft updated), but no WhatsApp reply goes out.
            no_reply_reason = (
                decision.reason if not decision.send_reply else "auto_reply_disabled"
            )
            logger.info(
                "evolution_inbound_held",
                sender=masked,
                allowed_sender=True,
                auto_reply_decision="hold",
                no_auto_reply_reason=no_reply_reason,
                order_touched=bool(order_result),
            )
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "no_auto_reply")

        processed += 1

    return {"status": "ok", "stored": True, "processed": processed, "skipped": skipped}
