"""Evolution API inbound webhook — real WhatsApp messages → Supabase.

Point your Evolution instance's webhook at POST {backend}/webhooks/evolution
(event: messages.upsert). For each inbound message from an APPROVED test number:

  1. IDEMPOTENCY — a redelivered event (same wa_message_id) is dropped: no
     duplicate message, no double state advance, no double confirm.
  2. Store the inbound message (text or the interactive selection's display text).
  3. ESCALATION (refund/complaint/damage/…) — raise a flag + ticket, mark Human
     Needed, never auto-resolve. Interrupts a booking too.
  4. BOOKING — routed through the deterministic state machine
     (services/booking_flow.py). The DB (orders.conversation_state) is the source
     of truth for the step; the LLM never decides a transition, invents a service/
     slot/date/price, or confirms a booking. A draft order is created only when a
     booking actually starts (state waiting_for_service, all fields null) and is
     flipped to a confirmed operational order EXACTLY once, on explicit confirm.
     Interactive lists/buttons are sent via Evolution with a numbered-text
     fallback if the interactive send fails.
  5. Everything else (greetings / general questions) keeps the existing
     domain/auto-reply behaviour.

Safety: non-approved senders are dropped before anything is stored. SQLite mode
acknowledges but stores nothing. No raw phone/address is ever logged.
"""
import datetime as _dt

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
    orders_repo,
    slots_repo,
    tickets_repo,
)
from services import booking_flow, order_store
from services.auto_reply import SENDER_NOT_ALLOWED, should_auto_reply
from services.escalation import detect_escalation
from services.privacy import mask_phone, normalize_e164
from settings import get_settings

router = APIRouter(prefix="/webhooks", tags=["evolution-webhook"])
logger = structlog.get_logger()

_GST = _dt.timezone(_dt.timedelta(hours=4))  # Dubai (no DST)

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

_BOOKING_SELECTION_PREFIXES = ("service:", "slot:", "instruction:", "date:", "change:")
_BOOKING_SELECTION_IDS = {"confirm_booking", "change_details", "cancel_booking"}


def _today() -> _dt.date:
    return _dt.datetime.now(_GST).date()


def _is_booking_selection(selection_id: str | None) -> bool:
    if not selection_id:
        return False
    return selection_id in _BOOKING_SELECTION_IDS or any(
        selection_id.startswith(p) for p in _BOOKING_SELECTION_PREFIXES
    )


def _booking_from_row(row: dict, *, profile_name: str | None = None,
                      verified_name: str | None = None) -> booking_flow.Booking:
    return booking_flow.Booking(
        conversation_state=row.get("conversation_state"),
        customer_name=row.get("customer_name"),
        service_id=row.get("service_id"),
        service_name_snapshot=row.get("service_name_snapshot") or row.get("service"),
        pickup_date=row.get("pickup_date"),
        pickup_slot_id=row.get("pickup_slot_id"),
        pickup_slot_label=row.get("pickup_slot"),
        pickup_address=row.get("pickup_address"),
        pickup_area=row.get("pickup_area") or row.get("area"),
        pickup_instruction_code=row.get("pickup_instruction_code"),
        pickup_instruction_text=row.get("pickup_instruction_text"),
        # transient context: an unverified profile name (offered, never auto-saved)
        # and a previously confirmed name for this customer (offered for reuse).
        whatsapp_profile_name=profile_name,
        verified_name=verified_name,
    )


def _final_confirmation_text(row: dict) -> str:
    d = row.get("pickup_date")
    date_str = d.strftime("%A, %d %B") if isinstance(d, _dt.date) else "—"
    lines = [
        "✅ Booking confirmed! Thank you.",
        f"Order {row.get('order_id')}",
        f"Service: {row.get('service_display_name') or row.get('service') or '—'}",
        f"Pickup date: {date_str}",
        f"Pickup time: {row.get('pickup_slot') or '—'}",
        f"Address: {row.get('pickup_address') or '—'}",
        f"Instructions: {row.get('pickup_instruction_text') or 'No additional instructions'}",
        "Our team will reach out shortly to finalise the details.",
    ]
    return "\n".join(lines)


async def _send_reply(channel, phone: str, reply) -> str:
    """Send a booking reply. Interactive list/buttons are attempted via Evolution
    only when EVOLUTION_USE_INTERACTIVE=true; otherwise (the default, because this
    Evolution/WhatsApp build does not render them) we send a plain numbered-text
    version of the prompt. On any interactive send failure we also fall back to
    numbered text. Either way a numeric reply ("2") is mapped back to the real
    option id by the FSM. Returns the text stored as the agent message."""
    interactive = reply.interactive
    if interactive is None:
        await channel.send_text(to_phone=phone, text=reply.text)
        return reply.text
    settings = get_settings()
    # Lists and buttons are gated independently: native lists render reliably on
    # this Evolution build, native buttons do not (see settings). A disabled kind
    # is sent as numbered text, which the FSM resolves back to the real option id.
    use_native = (settings.evolution_use_interactive if interactive.kind == "list"
                  else settings.evolution_use_buttons)
    if not use_native:
        numbered = booking_flow.numbered_fallback(interactive)
        await channel.send_text(to_phone=phone, text=numbered)
        logger.info("evolution_numbered_sent", kind=interactive.kind)
        return numbered
    try:
        if interactive.kind == "list":
            await channel.send_list(
                to_phone=phone,
                body=interactive.body,
                button_text=interactive.button_text or "Choose",
                section_title=interactive.section_title or "Options",
                header=interactive.header or "",
                rows=[{"id": o.id, "title": o.title, "description": o.description}
                      for o in interactive.options],
            )
        else:
            await channel.send_buttons(
                to_phone=phone,
                body=interactive.body,
                header=interactive.header or "",
                buttons=[{"id": o.id, "title": o.title} for o in interactive.options],
            )
        return interactive.body
    except Exception as exc:  # noqa: BLE001 - fall back to numbered text, never fail
        logger.warning("evolution_interactive_failed", kind=interactive.kind, error=str(exc))
        fallback = booking_flow.numbered_fallback(interactive)
        await channel.send_text(to_phone=phone, text=fallback)
        logger.info("evolution_fallback_sent", kind=interactive.kind)
        return fallback


async def _deliver(channel, phone: str, convo_id: str, reply) -> None:
    """Send a BookingReply and store it as an agent message. Never raises — a
    provider send error is logged but must not fail the webhook."""
    try:
        sent = await _send_reply(channel, phone, reply)
        await messages_repo.add_message(convo_id, "agent", sent, status="sent",
                                        metadata={"booking_state": reply.state})
    except Exception as exc:  # noqa: BLE001
        logger.warning("evolution_send_failed", error=str(exc))


def _order_status_text(order: dict | None) -> str:
    if not order:
        return ("I couldn't find a recent order for you. Reply 'new order' to book "
                "a pickup.")
    label = order_store.status_label(order.get("status") or "")
    return f"Your most recent order {order.get('order_id')} is currently: {label}."


async def _raise_support(conversation_id: str, order_uuid) -> None:
    """Route the conversation to a human (customer asked for support)."""
    flag_type, priority, team = _DEFAULT_FLAG
    await conversations_repo.set_flagged(
        conversation_id, reason="customer requested support", priority=priority, team=team)
    await flags_repo.create(
        conversation_id=conversation_id, flag_type=flag_type, priority=priority,
        assigned_team=team, reason="Customer asked to talk to support", order_id=order_uuid)
    await tickets_repo.create_or_update(
        conversation_id=conversation_id, ticket_type=flag_type, priority=priority,
        assigned_team=team, title="Support requested — WhatsApp",
        description="Customer asked to talk to support from WhatsApp.", order_uuid=order_uuid)


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

    if not database.is_supabase_mode():
        return {"status": "ok", "stored": False, "processed": 0,
                "reason": "booking requires DATABASE_MODE=supabase"}

    mode = settings.agent_operating_mode  # test | live | paused (safe default = paused)
    allowed = settings.allowed_auto_reply_numbers
    # Sending an automated reply requires BOTH the mode to allow replies (test/live)
    # AND Evolution to be live-ready.
    live = settings.agent_replies_enabled and settings.evolution_live_ready

    processed = 0
    skipped = 0
    duplicates = 0
    for msg in inbound:
        sender = normalize_e164(msg["phone"])
        masked = mask_phone(sender)

        # Sender gate: LIVE mode processes every valid customer; TEST and PAUSED
        # only process allow-listed test numbers (others are ignored entirely).
        if mode != "live" and sender not in allowed:
            skipped += 1
            logger.info("evolution_inbound_skipped", sender=masked, allowed_sender=False,
                        agent_mode=mode, no_auto_reply_reason=SENDER_NOT_ALLOWED)
            continue

        wa_id = msg.get("wa_message_id") or None
        if await messages_repo.wa_message_seen(wa_id):
            duplicates += 1
            logger.info("evolution_duplicate_ignored", sender=masked, wa_message_id=bool(wa_id))
            continue

        text = msg.get("text") or ""
        inbound_obj = booking_flow.Inbound(
            text=text,
            selection_id=msg.get("selection_id"),
            latitude=msg.get("latitude"),
            longitude=msg.get("longitude"),
        )

        customer = await customers_repo.get_or_create_by_phone(msg["phone"], msg["name"])
        convo = await conversations_repo.get_or_create_for_customer(
            customer["id"], external_id=f"evo:{sender}"
        )

        stored_text = text or (msg.get("selection_id") or "shared location")
        inbound_msg = await messages_repo.add_message(
            convo["id"], "customer", stored_text, status="received", wa_message_id=wa_id,
            metadata={"selection_id": msg.get("selection_id"),
                      "has_location": inbound_obj.is_location},
        )
        await conversations_repo.register_inbound(convo["id"], stored_text)

        # --- ESCALATION (interrupts everything, never auto-resolves) -----------
        category = detect_escalation(text)
        if category:
            flag_type, priority, team = _ESCALATION_FLAG.get(category, _DEFAULT_FLAG)
            reason = category.replace("_", " ")
            open_order = await orders_repo.get_open_for_conversation(convo["id"])
            order_uuid = open_order["id"] if open_order else None
            await conversations_repo.set_flagged(convo["id"], reason=reason, priority=priority, team=team)
            await flags_repo.create(conversation_id=convo["id"], flag_type=flag_type,
                                    priority=priority, assigned_team=team,
                                    reason=f"Agent flagged: {reason}", order_id=order_uuid)
            await tickets_repo.create_or_update(conversation_id=convo["id"], ticket_type=flag_type,
                                                priority=priority, assigned_team=team,
                                                title=f"{reason.title()} — WhatsApp",
                                                description=f"Raised from WhatsApp. Category: {reason}.",
                                                order_uuid=order_uuid)
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "human_needed")
            logger.info("evolution_inbound_escalation", sender=masked, flag_type=flag_type)
            processed += 1
            continue

        # --- PAUSED / human-takeover: store only, never auto-reply -------------
        # The message is already persisted above (ops can see it). We do NOT run
        # the booking state machine or send anything, so a human operator owns the
        # conversation and the AI never talks over them. AI resumes on the next
        # message once takeover ends / mode returns to test|live.
        if mode == "paused" or convo.get("status") == "human_takeover" or not live:
            reason = (
                "human_takeover" if convo.get("status") == "human_takeover"
                else "agent_paused" if mode == "paused"
                else "replies_disabled"
            )
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "no_auto_reply")
            logger.info("evolution_inbound_held", sender=masked, agent_mode=mode,
                        no_auto_reply_reason=reason)
            processed += 1
            continue

        # --- BOOKING routing (multi-order aware) --------------------------------
        # Route by whether there is an IN-PROGRESS DRAFT (status='draft'). A
        # confirmed/scheduled order is NOT an active workflow, so it never blocks a
        # NEW order — a single conversation can hold many workflows/orders
        # (spec §state-model).
        active_draft = await orders_repo.get_active_draft(convo["id"])
        draft_state = active_draft.get("conversation_state") if active_draft else None
        sel = inbound_obj.selection_id
        channel = EvolutionWhatsAppChannel.from_settings()
        booking_row = None
        reply = None
        # Name context for the FSM: the UNVERIFIED WhatsApp profile name (offered
        # for confirmation only) and any previously CONFIRMED name for this
        # customer (offered for reuse). Neither is ever saved without confirmation.
        profile_name = booking_flow.validate_name(customer.get("display_name") or msg.get("name"))
        verified_name = await orders_repo.get_confirmed_customer_name(customer["id"])

        def _booking(row):
            return _booking_from_row(row, profile_name=profile_name, verified_name=verified_name)

        if draft_state in booking_flow.ACTIVE_STATES:
            booking_row = active_draft
            # An explicit new-order intent DURING a draft with progress asks the
            # customer to continue or start over (active-draft protection).
            if (draft_state != booking_flow.RESUME_OR_NEW
                    and booking_flow.is_new_order_intent(text)
                    and booking_flow.has_progress(_booking(active_draft))):
                reply = booking_flow.resume_or_new_prompt()
            else:
                reply = await booking_flow.advance(_booking(active_draft), inbound_obj,
                                                   today=_today(), available_slots=slots_repo.available_slots)
        else:
            # No in-progress draft — free to start a new order or handle next-actions.
            latest = await orders_repo.get_latest_for_conversation(convo["id"])
            in_post_order = bool(latest and latest.get("conversation_state") == booking_flow.POST_ORDER)
            action = booking_flow.resolve_post_order_action(inbound_obj, numbered=in_post_order)

            if (action == booking_flow.NEW_ORDER
                    or booking_flow.is_book_pickup_intent(text)
                    or _is_booking_selection(sel)):
                booking_row = await orders_repo.start_booking(convo["id"], customer)  # idempotent
                # Capture a name volunteered in the OPENING message ("My name is
                # Sara. I need dry cleaning.") — persisted before the service list.
                opening_name = booking_flow.extract_name(text)
                if opening_name and not booking_row.get("customer_name"):
                    updated = await orders_repo.apply_booking_updates(
                        booking_row["id"], {"customer_name": opening_name},
                        booking_row.get("conversation_state") or "waiting_for_service")
                    if updated:
                        booking_row = updated
                    logger.info("customer_name_saved", sender=masked, source="provided")
                logger.info("booking_intent_detected", sender=masked, order=booking_row["order_id"])
                if _is_booking_selection(sel) or text.strip().isdigit():
                    reply = await booking_flow.advance(_booking(booking_row), inbound_obj,
                                                       today=_today(), available_slots=slots_repo.available_slots)
                else:
                    reply = booking_flow.begin_new_order() if latest else booking_flow.begin()
            elif action == booking_flow.CHECK_ORDER_STATUS:
                if live:
                    await _deliver(channel, msg["phone"], convo["id"], booking_flow.BookingReply(
                        text=_order_status_text(latest), state=booking_flow.POST_ORDER))
                logger.info("order_status_requested", sender=masked)
                processed += 1
                continue
            elif action == booking_flow.HUMAN_SUPPORT:
                await _raise_support(convo["id"], latest["id"] if latest else None)
                if inbound_msg:
                    await messages_repo.set_status(inbound_msg["id"], "human_needed")
                if live:
                    await _deliver(channel, msg["phone"], convo["id"], booking_flow.BookingReply(
                        text="Sure — I'll connect you with our team. They'll follow up "
                             "with you shortly.", state=booking_flow.POST_ORDER))
                logger.info("evolution_inbound_escalation", sender=masked, flag_type="handoff")
                processed += 1
                continue
            elif in_post_order:
                # Post-order context, message not understood -> re-show the actions.
                if live:
                    await _deliver(channel, msg["phone"], convo["id"], booking_flow.post_order_actions())
                processed += 1
                continue

        if reply is not None:
            order_uuid = booking_row["id"]
            if reply.start_new_order:
                # Abandon the current draft, spin up a fresh workflow, show services.
                await orders_repo.cancel_booking(order_uuid)
                new_row = await orders_repo.start_booking(convo["id"], customer)
                to_send = booking_flow.begin_new_order()
                await orders_repo.apply_booking_updates(new_row["id"], to_send.updates, to_send.state)
                logger.info("booking_restarted", sender=masked,
                            old=booking_row["order_id"], new=new_row["order_id"])
                if live:
                    await _deliver(channel, msg["phone"], convo["id"], to_send)
                processed += 1
                continue
            if reply.confirm_now:
                row, created_now = await orders_repo.confirm_booking(order_uuid)
                if row:
                    await orders_repo.set_conversation_state(row["id"], booking_flow.POST_ORDER)
                logger.info("booking_confirmed", sender=masked,
                            order=row["order_id"] if row else None, created_now=created_now)
                if live:
                    await _deliver(channel, msg["phone"], convo["id"], booking_flow.BookingReply(
                        text=_final_confirmation_text(row) if row else "Your booking is confirmed.",
                        state=booking_flow.POST_ORDER))
                    # Offer next actions (place another order / status / support).
                    await _deliver(channel, msg["phone"], convo["id"], booking_flow.post_order_actions())
                processed += 1
                continue
            elif reply.cancel_now:
                await orders_repo.cancel_booking(order_uuid)
                to_send = reply
                logger.info("booking_cancelled", sender=masked, order=booking_row["order_id"])
            else:
                await orders_repo.apply_booking_updates(order_uuid, reply.updates, reply.state)
                to_send = reply
                if reply.log_event:
                    logger.info("booking_step", sender=masked,
                                booking_event=reply.log_event, state=reply.state)

            if live:
                await _deliver(channel, msg["phone"], convo["id"], to_send)
            processed += 1
            continue

        # --- NON-BOOKING (greetings / general questions) -----------------------
        prior = await messages_repo.list_messages(convo["id"])
        history = [(m["sender_type"], m["message_text"]) for m in prior
                   if m["sender_type"] in ("customer", "agent")]
        welcome_sent = any(m["sender_type"] == "agent" for m in prior)
        decision = should_auto_reply(text, {"welcome_sent": welcome_sent})
        will_send = bool(decision.send_reply and live)

        if will_send:
            agent_reply = await handle_message(text=text, history=history, db=None)
            try:
                await EvolutionWhatsAppChannel.from_settings().send_text(
                    to_phone=msg["phone"], text=agent_reply.text)
                await messages_repo.add_message(convo["id"], "agent", agent_reply.text,
                                                status="sent", metadata={"intent": decision.intent})
                logger.info("evolution_auto_reply_sent", sender=masked)
            except Exception as exc:  # noqa: BLE001
                logger.warning("evolution_auto_reply_failed", sender=masked, error=str(exc))
        else:
            logger.info("evolution_inbound_held", sender=masked,
                        no_auto_reply_reason=decision.reason)
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "no_auto_reply")
        processed += 1

    return {"status": "ok", "stored": True, "processed": processed,
            "skipped": skipped, "duplicates": duplicates}
