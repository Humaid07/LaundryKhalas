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
import hashlib as _hashlib

import structlog
from fastapi import APIRouter, Request

from agents.whatsapp_agent.agent import handle_message
from agents.whatsapp_agent.booking_tools import BookingContext, run_booking_turn
from channels.evolution_whatsapp import EvolutionWhatsAppChannel, parse_evolution_webhook
from db import database
from db.repositories import (
    b2b_leads_repo,
    complaints_repo,
    conversations_repo,
    crm_repo,
    customers_repo,
    flags_repo,
    human_interventions_repo,
    messages_repo,
    orders_repo,
    pending_tasks_repo,
    slots_repo,
    tickets_repo,
    turns_repo,
)
from services import (
    abuse_classification,
    b2b,
    booking_flow,
    complaints,
    contact_identity,
    discount,
    human_intervention,
    location_capture,
    message_aggregation,
    message_completeness,
    money,
    order_confirmation,
    order_store,
    post_confirmation,
    reply_style,
    voice_fallback,
)
from services.auto_reply import SENDER_NOT_ALLOWED, should_auto_reply
from services.escalation import detect_escalation
from services import clock
from services.privacy import mask_phone, normalize_e164
from services.turn_service import TurnBuffer
from settings import get_settings

router = APIRouter(prefix="/webhooks", tags=["evolution-webhook"])
logger = structlog.get_logger()

_GST = _dt.timezone(_dt.timedelta(hours=4))  # Dubai (no DST)


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


_TURN_BUFFER: TurnBuffer | None = None


def get_turn_buffer() -> TurnBuffer:
    """Process-wide inbound message buffer (debounce timers live here). Rebuilt
    if the configured debounce/max window changes. Shared by the webhook (ingest)
    and startup recovery."""
    global _TURN_BUFFER
    s = get_settings()
    # The buffer's ``debounce`` is only the FALLBACK wait (used by recovery / when a
    # caller passes no adaptive value); the ACTIVE per-fragment wait is chosen by the
    # completeness classifier and passed into add_fragment. ``max`` is the hard cap.
    fallback = s.debounce_fragment_seconds
    max_s = s.max_aggregation_seconds
    if (_TURN_BUFFER is None
            or _TURN_BUFFER.debounce != float(fallback)
            or _TURN_BUFFER.max != float(max_s)):
        _TURN_BUFFER = TurnBuffer(turns_repo, debounce_seconds=fallback, max_seconds=max_s)
    return _TURN_BUFFER


async def recover_pending_turns() -> int:
    """Re-drive inbound turns left buffered / in-flight by a restart so a pending
    customer message still gets its one reply (spec §§21/27). Supabase-only and
    best-effort — it skips conversations now under human takeover so the AI never
    talks over an operator, and never blocks startup on error."""
    settings = get_settings()
    if not settings.whatsapp_message_aggregation_enabled:
        return 0
    buf = get_turn_buffer()
    live = settings.agent_replies_enabled and settings.evolution_live_ready

    async def _recovery_processor(conversation_id, combined, turn):
        convo = await conversations_repo.get_conversation(conversation_id)
        if not convo or convo.get("status") == "human_takeover":
            return None
        phone = await conversations_repo.get_customer_phone(conversation_id)
        if not phone:
            return None
        customer = {"id": convo.get("customer_id"), "display_name": None}
        await _process_reply(convo, customer, combined, phone=phone,
                             masked=mask_phone(phone), live=live, last_inbound_msg=None,
                             turn_id=(turn or {}).get("turn_id"))
        return None

    return await buf.recover(_recovery_processor)


async def _published_price_overrides() -> dict:
    """Current published/promotional unit prices for the booking quote, so the
    agent reflects a just-published price with no restart. Fail-safe: any error
    (no published version / DB down) → empty dict → the static catalogue price is
    used and no price is ever invented (task spec §24)."""
    try:
        from db import AsyncSessionLocal
        from services import price_resolver

        async with AsyncSessionLocal() as session:
            return await price_resolver.published_overrides(session, market="AE")
    except Exception:  # noqa: BLE001 — never let pricing lookup break the webhook
        return {}

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

# Flag types that represent a customer COMPLAINT (→ structured complaint record +
# review task + empathetic ack). B2B/handoff/legal go through their own flows.
_COMPLAINT_FLAG_TYPES = frozenset({
    "refund_request", "payment_issue", "damaged_item", "missing_item",
    "complaint", "late_delivery",
})

# Professional temporary-failure reply (spec §29). Sent — and the conversation
# flagged for a human — when the AI turn fails, so the customer is never left in
# silence and no false booking/confirmation is implied.
_AI_FALLBACK_TEXT = (
    "Sorry — I'm having trouble completing that right now. I've flagged this to our "
    "team and someone will follow up with you shortly."
)

# The ONE approved refund acknowledgement. A refund is NEVER handled by the AI:
# the conversation is durably handed to Operations (human_takeover) and this is
# the single calm notice sent — it never approves/promises/quotes a refund.
_REFUND_ACK_TEXT = (
    "I'm sorry about this. I've forwarded your refund request to our Operations team "
    "for review. Please hold on while one of our executives gets in touch with you."
)

_BOOKING_SELECTION_PREFIXES = ("service:", "sub:", "item:", "slot:", "instruction:",
                               "date:", "change:")
_BOOKING_SELECTION_IDS = {"confirm_booking", "change_details", "cancel_booking",
                          "add_item", "items_done"}


def _today() -> _dt.date:
    # Market-local calendar date via the central clock (business timezone).
    return clock.today()


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
        line_items=row.get("line_items"),
        browse_service_code=row.get("browse_service_code"),
        pending_item_code=row.get("pending_item_code"),
        pickup_date=row.get("pickup_date"),
        pickup_slot_id=row.get("pickup_slot_id"),
        pickup_slot_label=row.get("pickup_slot"),
        pickup_address=row.get("pickup_address"),
        pickup_area=row.get("pickup_area") or row.get("area"),
        pickup_instruction_code=row.get("pickup_instruction_code"),
        pickup_instruction_text=row.get("pickup_instruction_text"),
        discount_requested=bool(row.get("discount_requested")),
        # transient context: an unverified profile name (offered, never auto-saved)
        # and a previously confirmed name for this customer (offered for reuse).
        whatsapp_profile_name=profile_name,
        verified_name=verified_name,
    )


def _final_confirmation_text(row: dict) -> str:
    d = row.get("pickup_date")
    date_str = d.strftime("%A, %d %B") if isinstance(d, _dt.date) else "—"
    name = row.get("customer_name")
    lines = ["Booking confirmed. Thank you.", f"Order {row.get('order_id')}"]
    if name:
        lines.append(f"Name: {name}")
    lines.append(f"Service: {row.get('service_display_name') or row.get('service') or '—'}")
    total = row.get("estimated_total")
    if total is not None:
        # FINAL customer price — already VAT-inclusive, no 5% added, and net of
        # any automatic order discount. No VAT/tax wording (spec §§4/10).
        discount_amount = row.get("discount_amount")
        if discount_amount and float(discount_amount) > 0:
            pct = row.get("discount_percentage")
            pct_str = money.format_money(pct) if pct is not None else "15"
            lines.append(f"Subtotal: AED {money.format_money(row.get('eligible_subtotal'))}")
            lines.append(f"Automatic {pct_str}% discount: AED {money.format_money(discount_amount)} off")
        label = "Estimated price" if row.get("pricing_is_estimated") else "Price"
        lines.append(f"{label}: AED {money.format_money(total)}")
    pin_present = row.get("pickup_latitude") is not None and row.get("pickup_longitude") is not None
    lines += [
        f"Pickup date: {date_str}",
        f"Pickup time: {row.get('pickup_slot') or '—'}",
        f"Address: {row.get('pickup_address') or '—'}",
        f"Location pin: {'Received' if pin_present else 'Not received'}",
        f"Instructions: {row.get('pickup_instruction_text') or 'No additional instructions'}",
        "Our team will reach out shortly to finalise the details.",
    ]
    return "\n".join(lines)


def _normalize_text(convo_id: str | None, text: str | None, *, source: str) -> str:
    """Run the deterministic no-dash style normaliser on ONE customer-facing string
    immediately before it is sent (spec 2026-07-31). Logs safe metadata only — the
    conversation id, how many dashes were found, which rules fired, and whether the
    result validated clean — never the full customer message (privacy)."""
    result = reply_style.normalize_customer_reply(text)
    if result.changed or not result.valid:
        logger.info(
            "customer_reply_style_normalized",
            conversation=convo_id,
            source=source,
            dash_count=result.dash_count,
            rules_applied=result.rules_applied,
            valid=result.valid,
        )
    if result.emoji_count:
        # Emojis are forbidden in customer-facing replies (spec 2026-08-01). Log a
        # safe event (count only, never the message) when the validator removes any.
        logger.info(
            "customer_reply_emoji_removed",
            conversation=convo_id,
            source=source,
            emoji_count=result.emoji_count,
        )
    if result.exclaim_count:
        # Routine replies should not use exclamation marks (spec 2026-08-01) — the
        # validator replaces them with full stops. Safe event (count only).
        logger.info(
            "customer_reply_exclamation_normalized",
            conversation=convo_id,
            source=source,
            exclaim_count=result.exclaim_count,
        )
    return result.text


def _normalize_reply(convo_id: str | None, reply) -> None:
    """Normalise a BookingReply's customer-facing prose in place: the text body and,
    when present, the interactive prompt body. Structured option labels (service
    names, numbered choices) are left untouched — they are labels, not prose."""
    if getattr(reply, "text", None):
        reply.text = _normalize_text(convo_id, reply.text, source="booking_text")
    interactive = getattr(reply, "interactive", None)
    if interactive is not None and getattr(interactive, "body", None):
        interactive.body = _normalize_text(convo_id, interactive.body, source="booking_interactive")


async def _send_reply(channel, phone: str, reply) -> str:
    """Send a booking reply. Interactive list/buttons are attempted via Evolution
    only when EVOLUTION_USE_INTERACTIVE=true; otherwise (the default, because this
    Evolution/WhatsApp build does not render them) we send a plain numbered-text
    version of the prompt. On any interactive send failure we also fall back to
    numbered text. Either way a numeric reply ("2") is mapped back to the real
    option id by the FSM. Returns the text stored as the agent message."""
    interactive = reply.interactive
    if interactive is None:
        # Empty-text guard: never send an empty WhatsApp message (spec §2). If a
        # text reply is somehow blank, substitute the safe fallback so the send
        # is meaningful rather than silent/rejected.
        text = (reply.text or "").strip() or _AI_FALLBACK_TEXT
        await channel.send_text(to_phone=phone, text=text)
        return text
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


# Brief, deterministic gratitude reply after a confirmed order — no booking
# content, no order summary, no upsell (spec: post-confirmation THANK_YOU_RESPONSE).
_THANK_YOU_TEXT = "You're welcome."


def _reply_idem_key(turn_id: str | None, reply) -> str | None:
    """Deterministic outbound idempotency key for ONE logical reply of ONE turn:
    sha1(turn_id | workflow_state | reply body). Returns None when there is no
    logical turn id (aggregation-off legacy path), where wa_message_seen already
    dedupes; keying on content alone there could wrongly drop a legitimate repeat.
    Distinct replies within a turn (e.g. confirmation + next-actions) get distinct
    keys via their differing body/state, so only a true re-send is suppressed."""
    if not turn_id:
        return None
    body = reply.interactive.body if getattr(reply, "interactive", None) else (reply.text or "")
    raw = f"{turn_id}|{reply.state or ''}|{(body or '').strip()}"
    return _hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def _deliver(channel, phone: str, convo_id: str, reply, *, turn_id: str | None = None) -> None:
    """Send a BookingReply and store it as an agent message. Never raises — a
    provider send error is logged but must not fail the webhook. Idempotent per
    logical turn: a reply whose idem key was already delivered is skipped, so a
    redelivered webhook / restart re-drive / retry never double-sends (spec §§
    duplicate-prevention)."""
    # Normalise customer-facing prose (no-dash style) BEFORE the idem key is derived
    # from the body, so dedup keys off the exact text the customer receives.
    _normalize_reply(convo_id, reply)
    idem_key = _reply_idem_key(turn_id, reply)
    try:
        if idem_key and await messages_repo.agent_reply_key_seen(convo_id, idem_key):
            logger.info("duplicate_outbound_prevented", conversation=convo_id,
                        idempotency_reused=True, response_state=reply.state)
            return
        sent = await _send_reply(channel, phone, reply)
        await messages_repo.add_message(convo_id, "agent", sent, status="sent",
                                        metadata={"booking_state": reply.state,
                                                  "idem_key": idem_key, "turn_id": turn_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("evolution_send_failed", error=str(exc))


async def _send_plain(convo_id: str, phone: str, text: str, *, kind: str) -> None:
    """Send a plain-text agent message (voice fallback / handover) and store it.
    Idempotent per (conversation, kind) so a redelivery never double-sends."""
    try:
        idem = f"{convo_id}:{kind}"
        if await messages_repo.agent_reply_key_seen(convo_id, idem):
            logger.info("duplicate_outbound_prevented", conversation=convo_id, kind=kind)
            return
        text = _normalize_text(convo_id, text, source=kind)
        await EvolutionWhatsAppChannel.from_settings().send_text(to_phone=phone, text=text)
        await messages_repo.add_message(convo_id, "agent", text, status="sent",
                                        metadata={"kind": kind, "idem_key": idem})
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_reply_failed", kind=kind, error=str(exc))


async def _handle_unprocessable_voice(convo, customer, sender, masked, wa_id, inbound_msg, *, live, mode) -> None:
    """Voice-note handling (spec scenarios 1-4). The system has no transcription,
    so audio is never sent to the model: first note → one text-fallback ask; second
    DISTINCT note → human intervention + handover; duplicates/holds → store only."""
    convo_id = convo["id"]
    state_row = await conversations_repo.get_voice_state(convo_id)
    state = voice_fallback.VoiceState(
        count=state_row.get("count") or 0,
        last_message_id=state_row.get("last_message_id"),
        escalation_status=state_row.get("escalation_status") or "none",
    )
    takeover_active = convo.get("status") == "human_takeover"
    logger.info("voice_message_received", sender=masked, wa_message_id=bool(wa_id))
    decision = voice_fallback.decide_voice_message(state, audio_message_id=wa_id, takeover_active=takeover_active)

    # Persist counters BEFORE replying (survives restart; counted by unique id).
    await conversations_repo.set_voice_state(
        convo_id, count=decision.new_count, last_message_id=decision.new_last_message_id,
        escalation_status=decision.new_status,
        mark_fallback_sent=(decision.action == voice_fallback.VoiceAction.FIRST_FALLBACK),
    )
    if inbound_msg:
        await messages_repo.set_status(inbound_msg["id"], "no_auto_reply")

    can_reply = live and mode != "paused"

    if decision.action == voice_fallback.VoiceAction.DUPLICATE_IGNORED:
        logger.info("duplicate_voice_message_ignored", sender=masked)
        return
    if decision.action == voice_fallback.VoiceAction.HOLD:
        logger.info("evolution_inbound_held", sender=masked, no_auto_reply_reason="voice_escalated_or_takeover")
        return
    if decision.action == voice_fallback.VoiceAction.FIRST_FALLBACK:
        logger.info("voice_text_fallback_requested", sender=masked)
        if can_reply and not takeover_active:
            await _send_plain(convo_id, sender, decision.reply_text, kind="voice_text_fallback")
        return
    # ESCALATE — create the human-intervention case, pause AI, one handover reply.
    logger.info("repeated_voice_message_detected", sender=masked, reason=decision.escalation_reason)
    try:
        await conversations_repo.start_human_takeover(convo_id, operator_name=None)
        await conversations_repo.set_handoff_reason(convo_id, decision.escalation_reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_takeover_failed", sender=masked, error=str(exc))
    logger.info("voice_human_intervention_created", sender=masked, reason=decision.escalation_reason)
    try:  # notify Operations = surface via the takeover queue + CRM refresh (best-effort)
        await crm_repo.recompute_for_customer(customer["id"])
    except Exception:  # noqa: BLE001
        pass
    if can_reply:
        await _send_plain(convo_id, sender, decision.reply_text, kind="voice_handover")


async def _persist_identity(customer: dict, msg: dict, masked: str) -> None:
    """Persist the normalized WhatsApp number + validated profile name onto the
    customer (spec §identity). Backend-authoritative; the repo guards an
    explicit/confirmed name from being overwritten by the WhatsApp profile."""
    try:
        e164, num_ok = contact_identity.normalize_whatsapp_sender_number(msg.get("phone"))
        prior_source = customer.get("customer_name_source")
        confirmed = customer.get("customer_name") if prior_source in ("CUSTOMER_PROVIDED", "CONFIRMED") else None
        resolved = contact_identity.resolve_customer_identity(
            confirmed_name=confirmed, whatsapp_profile_name=msg.get("name"))
        await customers_repo.update_channel_identity(
            customer["id"], whatsapp_number=msg.get("phone"),
            normalized_number=e164 if num_ok else None, number_verified=num_ok,
            profile_name_raw=msg.get("name"), resolved_name=resolved.name,
            name_source=resolved.source, name_confidence=resolved.confidence,
            name_requires_confirmation=resolved.requires_confirmation)
        logger.info("whatsapp_number_normalized", sender=masked, valid=num_ok)
        if (msg.get("name") or "").strip() and confirmed is None:
            if resolved.source == contact_identity.SOURCE_WHATSAPP_PROFILE:
                logger.info("whatsapp_profile_name_accepted", sender=masked)
            else:
                logger.info("whatsapp_profile_name_rejected", sender=masked)
    except Exception as exc:  # noqa: BLE001 — identity persistence must never break intake
        logger.warning("identity_persist_failed", sender=masked, error=str(exc))


async def _persist_location(convo_id: str, msg: dict, wa_id: str | None, masked: str) -> None:
    """Persist structured WhatsApp location metadata onto the active draft (spec
    §location-pin). The pin drives routing; coordinates are only ever written from
    a real Evolution location event — never invented."""
    try:
        cap = location_capture.process_whatsapp_location(
            msg.get("location_event")
            or {"latitude": msg.get("latitude"), "longitude": msg.get("longitude")})
        if not cap.ok:
            return
        draft = await orders_repo.get_active_draft(convo_id)
        if not draft:
            logger.info("whatsapp_location_received", sender=masked, has_draft=False)
            return
        await orders_repo.apply_booking_updates(
            draft["id"],
            {
                "pickup_latitude": cap.latitude, "pickup_longitude": cap.longitude,
                "location_name": cap.location_name, "location_provider_address": cap.provider_address,
                "location_type": cap.location_type, "location_accuracy": cap.accuracy,
                "location_message_id": wa_id, "location_source": "whatsapp_pin",
                "location_received_at": _dt.datetime.now(_GST), "location_pin_status": "received",
            },
            draft.get("conversation_state") or booking_flow.WAITING_FOR_ADDRESS,
        )
        logger.info("whatsapp_location_received", sender=masked, has_draft=True)
    except Exception as exc:  # noqa: BLE001 — enrichment must never break the booking turn
        logger.warning("location_persist_failed", sender=masked, error=str(exc))


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


async def _process_reply(convo: dict, customer: dict, combined, *, phone: str,
                         masked: str, live: bool, last_inbound_msg: dict | None,
                         turn_id: str | None = None) -> None:
    """Generate + send ONE agent reply for a combined customer turn.

    The per-turn processor: runs the booking routing (Claude orchestration → FSM
    → non-booking) exactly ONCE on the combined text and sends a single reply.
    Extracted so the inline path (aggregation off) and the debounce flush
    (aggregation on) share identical behaviour. Access/idempotency/escalation/
    takeover gates already ran per fragment in the webhook loop before this."""
    settings = get_settings()
    text = combined.text

    # --- Abuse / threat safety gate (BEFORE any AI or booking work) ----------
    # Classify the COMBINED turn deterministically (fast, no LLM). On a genuine
    # abuse/threat: persist the human-intervention state + PAUSE the conversation
    # in ONE committed transaction, THEN send the single calm holding message.
    # Ordering matters — a concurrent later message must see the paused state and
    # be stored, never answered. Idempotent: a duplicate turn / retry reuses the
    # existing event and never resends the notice. Never crashes the turn.
    if database.is_supabase_mode():
        try:
            prior = await human_interventions_repo.abuse_event_count(convo["id"])
            classification = abuse_classification.classify(text, prior_abuse_event_count=prior)
            if classification.human_intervention_required:
                outcome = await human_intervention.trigger_from_classification(
                    convo["id"], classification,
                    flagged_message_id=(last_inbound_msg or {}).get("id"),
                    flagged_turn_id=turn_id, combined_text=text)
                if outcome.should_send_notice and live:
                    await _deliver(
                        EvolutionWhatsAppChannel.from_settings(), phone, convo["id"],
                        booking_flow.BookingReply(text=outcome.holding_message,
                                                  state="human_takeover"),
                        turn_id=turn_id)
                return  # AI paused — do NOT run booking / Anthropic for this turn
        except Exception as exc:  # noqa: BLE001 — the safety gate must never crash a turn
            logger.warning("abuse_gate_error", sender=masked, error=str(exc))

    inbound_obj = booking_flow.Inbound(
        text=text, selection_id=combined.selection_id,
        latitude=combined.latitude, longitude=combined.longitude,
    )
    # Exclude THIS turn's own fragments from the history we hand the model.
    current_texts = set(combined.fragments)

    active_draft = await orders_repo.get_active_draft(convo["id"])

    # Sticky discount-request flag: once the customer asks for a discount / better
    # rate ("make it cheaper", "best rate", "that's expensive"), record it on the
    # open order so the pricing engine can apply the 20%-over-AED-200 tier when the
    # exact total is known. Never invents a discount here — only records intent.
    if active_draft and not active_draft.get("discount_requested") \
            and discount.detect_discount_request(text):
        logger.info("discount_request_detected", sender=masked, order=active_draft.get("order_id"))
        # Record intent AND immediately re-price the persisted draft so the FINAL
        # total reflects the applicable discount right away (spec: never leave the
        # pre-discount amount active). The pricing engine — not this code — decides
        # the rule/percentage; re-quoting is deterministic + idempotent (spec §9).
        state = active_draft.get("conversation_state") or booking_flow.WAITING_FOR_SERVICE
        updates: dict = {"discount_requested": True}
        reprice = booking_flow.pricing_updates_for_row(active_draft, discount_requested=True)
        if reprice:
            updates.update(reprice)
            logger.info(
                "discount_rule_resolved", sender=masked, order=active_draft.get("order_id"),
                rule_code=reprice.get("discount_rule_code"),
                percentage=reprice.get("discount_percentage"),
                pre_discount_total=reprice.get("eligible_subtotal"),
                discount_amount=reprice.get("discount_amount"),
                final_total=reprice.get("estimated_total"))
            event = "discount_applied" if reprice.get("discount_amount") else "discount_not_applied"
            logger.info(event, sender=masked, order=active_draft.get("order_id"),
                        final_total=reprice.get("estimated_total"))
        updated = await orders_repo.apply_booking_updates(active_draft["id"], updates, state)
        if updated:
            active_draft = updated
            logger.info("order_total_recalculated", sender=masked,
                        order=active_draft.get("order_id"),
                        final_total=active_draft.get("estimated_total"))

    draft_state = active_draft.get("conversation_state") if active_draft else None
    sel = inbound_obj.selection_id
    channel = EvolutionWhatsAppChannel.from_settings()
    booking_row = None
    reply = None
    profile_name = booking_flow.validate_name(customer.get("display_name"))
    verified_name = await orders_repo.get_confirmed_customer_name(customer["id"])

    def _booking(row):
        return _booking_from_row(row, profile_name=profile_name, verified_name=verified_name)

    # --- Claude-orchestrated conversation (natural language, default path) ---
    if settings.anthropic_booking_orchestration and settings.live_llm_ready:
        # POST-CONFIRMATION TERMINAL BOUNDARY (spec: a confirmed order is a hard
        # stop). With NO active draft, the booking flow is over. A stale/duplicate
        # confirmation, a bare ack, an empty/interactive-only turn, or a re-driven
        # old turn must NOT run a booking turn — that is exactly what produced the
        # spurious discount/upsell/re-confirm/goodbye chatter (a missing draft made
        # the model think a NEW booking had started). Only an explicit new request
        # (new order / edit / question) proceeds; gratitude gets one short reply.
        if active_draft is None:
            latest = await orders_repo.get_latest_for_conversation(convo["id"])
            if post_confirmation.is_confirmed_order(latest):
                kind = post_confirmation.classify_post_confirmation_turn(text, sel)
                if not kind.is_actionable:
                    if kind is post_confirmation.PostConfirmTurn.THANKS and live:
                        await _deliver(channel, phone, convo["id"],
                                       booking_flow.BookingReply(
                                           text=_THANK_YOU_TEXT, state=booking_flow.POST_ORDER),
                                       turn_id=turn_id)
                        logger.info("logical_turn_completed", sender=masked,
                                    conversation=convo["id"], order=latest.get("order_id"),
                                    final_response_type="THANK_YOU_RESPONSE", turn=turn_id)
                    else:
                        if last_inbound_msg:
                            await messages_repo.set_status(last_inbound_msg["id"], "no_auto_reply")
                        logger.info("post_confirmation_automation_blocked", sender=masked,
                                    conversation=convo["id"], order=latest.get("order_id"),
                                    reason="POST_CONFIRMATION_AUTOMATION_BLOCKED",
                                    turn_kind=kind.value, turn=turn_id)
                    return
        logger.info("anthropic_turn_started", sender=masked, conversation=convo["id"])
        prior = await messages_repo.list_messages(convo["id"])
        history = [(m["sender_type"], m["message_text"]) for m in prior
                   if m["sender_type"] in ("customer", "agent")
                   and m.get("message_text") and m["message_text"] not in current_texts]
        _market = (customer or {}).get("market")
        # Pin ONE approved AI persona to this customer on first contact (persistent,
        # never changes). Best-effort: a failure here must never block the reply.
        if customer:
            try:
                from db.repositories import customers_repo
                from services import persona_assignment
                await persona_assignment.ensure_assigned(customer, customers_repo)
            except Exception as exc:  # noqa: BLE001
                logger.info("persona_assign_skipped", error=str(exc))
        ctx = BookingContext(
            conversation_id=convo["id"], order_uuid=None, repo=orders_repo,
            today=clock.today(_market), available_slots=slots_repo.available_slots,
            customer=customer, profile_name=profile_name, verified_name=verified_name,
            now=clock.now(_market), market=_market)
        try:
            reply_text, result = await run_booking_turn(ctx, text=text, history=history)
        except Exception as exc:  # noqa: BLE001 — never leave the customer in silence
            logger.warning("anthropic_turn_failed", sender=masked, error=str(exc))
            reply_text, result = _AI_FALLBACK_TEXT, None
            await _raise_support(convo["id"], (active_draft or {}).get("id"))
            if last_inbound_msg:
                await messages_repo.set_status(last_inbound_msg["id"], "human_needed")
            logger.info("human_attention_required", sender=masked, reason="ai_turn_failed")

        if result is not None and "request_human_support" in (ctx.tool_calls or []):
            open_order = await orders_repo.get_open_for_conversation(convo["id"])
            await _raise_support(convo["id"], open_order["id"] if open_order else None)
            if last_inbound_msg:
                await messages_repo.set_status(last_inbound_msg["id"], "human_needed")
            logger.info("human_attention_required", sender=masked, reason="model_requested")

        fresh = await orders_repo.get_active_draft(convo["id"])
        state = (fresh or {}).get("conversation_state") or booking_flow.WAITING_FOR_SERVICE
        if live:
            await _deliver(channel, phone, convo["id"],
                           booking_flow.BookingReply(text=reply_text, state=state),
                           turn_id=turn_id)
        logger.info("anthropic_turn_delivered", sender=masked,
                    tools=(ctx.tool_calls or []),
                    provider=(result.provider if result else "fallback"),
                    tokens_in=(result.tokens_in if result else 0),
                    tokens_out=(result.tokens_out if result else 0),
                    cost_usd=(result.cost_usd if result else 0.0),
                    order=(fresh or {}).get("order_id"))
        return

    if draft_state in booking_flow.ACTIVE_STATES:
        booking_row = active_draft
        if (draft_state != booking_flow.RESUME_OR_NEW
                and booking_flow.is_new_order_intent(text)
                and booking_flow.has_progress(_booking(active_draft))):
            reply = booking_flow.resume_or_new_prompt()
        else:
            reply = await booking_flow.advance(_booking(active_draft), inbound_obj,
                                               today=_today(), available_slots=slots_repo.available_slots,
                                               price_overrides=await _published_price_overrides())
    else:
        latest = await orders_repo.get_latest_for_conversation(convo["id"])
        in_post_order = bool(latest and latest.get("conversation_state") == booking_flow.POST_ORDER)
        action = booking_flow.resolve_post_order_action(inbound_obj, numbered=in_post_order)

        if (action == booking_flow.NEW_ORDER
                or booking_flow.is_book_pickup_intent(text)
                or _is_booking_selection(sel)):
            booking_row = await orders_repo.start_booking(convo["id"], customer)  # idempotent
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
                                                   today=_today(), available_slots=slots_repo.available_slots,
                                                   price_overrides=await _published_price_overrides())
            else:
                reply = booking_flow.begin_new_order() if latest else booking_flow.begin()
        elif action == booking_flow.CHECK_ORDER_STATUS:
            if live:
                await _deliver(channel, phone, convo["id"], booking_flow.BookingReply(
                    text=_order_status_text(latest), state=booking_flow.POST_ORDER))
            logger.info("order_status_requested", sender=masked)
            return
        elif action == booking_flow.HUMAN_SUPPORT:
            await _raise_support(convo["id"], latest["id"] if latest else None)
            if last_inbound_msg:
                await messages_repo.set_status(last_inbound_msg["id"], "human_needed")
            if live:
                await _deliver(channel, phone, convo["id"], booking_flow.BookingReply(
                    text="Sure — I'll connect you with our team. They'll follow up "
                         "with you shortly.", state=booking_flow.POST_ORDER))
            logger.info("evolution_inbound_escalation", sender=masked, flag_type="handoff")
            return
        elif in_post_order:
            if live:
                await _deliver(channel, phone, convo["id"], booking_flow.post_order_actions())
            return

    if reply is not None:
        order_uuid = booking_row["id"]
        if reply.start_new_order:
            await orders_repo.cancel_booking(order_uuid)
            new_row = await orders_repo.start_booking(convo["id"], customer)
            to_send = booking_flow.begin_new_order()
            await orders_repo.apply_booking_updates(new_row["id"], to_send.updates, to_send.state)
            logger.info("booking_restarted", sender=masked,
                        old=booking_row["order_id"], new=new_row["order_id"])
            if live:
                await _deliver(channel, phone, convo["id"], to_send)
            return
        if reply.confirm_now:
            row, created_now = await orders_repo.confirm_booking(order_uuid)
            if row:
                await orders_repo.set_conversation_state(row["id"], booking_flow.POST_ORDER)
            logger.info("booking_confirmed", sender=masked,
                        order=row["order_id"] if row else None, created_now=created_now)
            # First-time confirm only: auto-assign a facility + notify it (mock-first).
            # Both steps are idempotent and never raise, so they can't break the
            # customer's confirmation reply.
            if row and created_now:
                # First-confirm side effects (facility assign + notify, campaign
                # attribution, CRM recompute). Shared with the Claude
                # `confirm_order` path so both behave identically — see
                # services/order_confirmation. Idempotent + never raises.
                await order_confirmation.apply_post_confirmation_effects(
                    dict(row), customer["id"])
            if live:
                await _deliver(channel, phone, convo["id"], booking_flow.BookingReply(
                    text=_final_confirmation_text(row) if row else "Your booking is confirmed.",
                    state=booking_flow.POST_ORDER))
                await _deliver(channel, phone, convo["id"], booking_flow.post_order_actions())
            return
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
            await _deliver(channel, phone, convo["id"], to_send)
        return

    # --- NON-BOOKING (greetings / general questions) -----------------------
    prior = await messages_repo.list_messages(convo["id"])
    history = [(m["sender_type"], m["message_text"]) for m in prior
               if m["sender_type"] in ("customer", "agent")]
    welcome_sent = any(m["sender_type"] == "agent" for m in prior)
    decision = should_auto_reply(text, {"welcome_sent": welcome_sent})
    will_send = bool(decision.send_reply and live)

    if will_send:
        agent_reply = await handle_message(text=text, history=history, db=None)
        out_text = (agent_reply.text or "").strip() or _AI_FALLBACK_TEXT
        out_text = _normalize_text(convo["id"], out_text, source="auto_reply")
        try:
            await EvolutionWhatsAppChannel.from_settings().send_text(
                to_phone=phone, text=out_text)
            await messages_repo.add_message(
                convo["id"], "agent", out_text, status="sent",
                metadata={
                    "intent": decision.intent,
                    "provider": agent_reply.provider,
                    "model": agent_reply.model,
                    "tokens_in": agent_reply.tokens_in,
                    "tokens_out": agent_reply.tokens_out,
                    "cost_usd": agent_reply.cost_usd,
                    "tool_calls": agent_reply.tool_calls,
                })
            logger.info("evolution_auto_reply_sent", sender=masked,
                        provider=agent_reply.provider, model=agent_reply.model,
                        tokens_in=agent_reply.tokens_in, tokens_out=agent_reply.tokens_out,
                        cost_usd=agent_reply.cost_usd, tool_calls=agent_reply.tool_calls)
        except Exception as exc:  # noqa: BLE001
            logger.warning("evolution_auto_reply_failed", sender=masked, error=str(exc))
    else:
        logger.info("evolution_inbound_held", sender=masked,
                    no_auto_reply_reason=decision.reason)
        if last_inbound_msg:
            await messages_repo.set_status(last_inbound_msg["id"], "no_auto_reply")


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
        # Persist WhatsApp-channel identity (normalized number + profile name +
        # profile-derived name) every inbound — cheap, idempotent, never clobbers
        # an explicit/confirmed customer name.
        await _persist_identity(customer, msg, masked)

        stored_text = text or (msg.get("selection_id") or "shared location")
        inbound_msg = await messages_repo.add_message(
            convo["id"], "customer", stored_text, status="received", wa_message_id=wa_id,
            # selection_id + location coords are stored so a turn can be
            # reconstructed from the DB after a restart (turn aggregation §21).
            metadata={"selection_id": msg.get("selection_id"),
                      "has_location": inbound_obj.is_location,
                      "latitude": msg.get("latitude"),
                      "longitude": msg.get("longitude")},
        )
        await conversations_repo.register_inbound(convo["id"], stored_text)

        # --- UNPROCESSABLE VOICE / AUDIO (spec scenarios 1-4) ------------------
        # Detect media BEFORE any model call so the agent never hallucinates a
        # transcript. First voice note → text fallback; second distinct → human
        # intervention + handover; duplicates/held → store only.
        media_kind = msg.get("media_kind") or "text"
        if media_kind == "audio":
            await _handle_unprocessable_voice(
                convo, customer, sender, masked, wa_id, inbound_msg, live=live, mode=mode
            )
            processed += 1
            continue
        # A valid text/interactive turn clears any pending voice-escalation state.
        if media_kind in ("text", "interactive") and (text or "").strip():
            try:
                await conversations_repo.reset_voice_state(convo["id"])
            except Exception:  # noqa: BLE001
                pass

        # Structured location capture (enrich the active draft; pin drives routing).
        # Runs in addition to the normal booking turn — never invents coordinates.
        if msg.get("location_event") or msg.get("latitude") is not None:
            await _persist_location(convo["id"], msg, wa_id, masked)

        # --- ESCALATION (interrupts everything, never auto-resolves) -----------
        category = detect_escalation(text)
        # IDEMPOTENT HANDOVER: if a human already owns this conversation (e.g. a
        # refund handover already paused the AI), do NOT create a second flag /
        # complaint / acknowledgement and never run the model — just store the
        # message for the operator. One notice per takeover (spec: idempotency key
        # conversation + case + REFUND_HUMAN_INTERVENTION_NOTICE).
        if category and convo.get("status") == "human_takeover":
            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "human_needed")
            if category == "refund":
                logger.info("refund_notice_duplicate_prevented", sender=masked)
            logger.info("evolution_inbound_held", sender=masked,
                        no_auto_reply_reason="human_takeover")
            processed += 1
            continue
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

            # Structured complaint + durable review task for complaint-type flags
            # (B2B/handoff go through their own flows). Best-effort — a failure here
            # must not stop the escalation handoff.
            order_ref = open_order["order_id"] if open_order else None
            has_order_ref = bool(order_ref) or "LK-" in (text or "").upper()
            if flag_type in _COMPLAINT_FLAG_TYPES:
                try:
                    complaint_category = complaints.classify_category(text, category)
                    complaint = await complaints_repo.create(
                        customer_id=customer["id"], conversation_id=convo["id"],
                        order_id=order_uuid, order_ref=order_ref,
                        category=complaint_category,
                        description=stored_text,
                        requested_resolution=complaints.detect_requested_resolution(text),
                        urgency=complaints.urgency_from_priority(priority),
                    )
                    await pending_tasks_repo.create(
                        "AWAITING_COMPLAINT_REVIEW",
                        customer_id=customer["id"], conversation_id=convo["id"],
                        order_id=order_uuid,
                        complaint_id=(complaint or {}).get("id"),
                        notes=f"Complaint {complaint.get('complaint_ref') if complaint else ''}: {reason}",
                    )
                    logger.info("complaint_created", sender=masked,
                                category=complaint_category,
                                ref=(complaint or {}).get("complaint_ref"))
                except Exception as exc:  # noqa: BLE001 - never break the handoff
                    logger.warning("complaint_create_failed", sender=masked, error=str(exc))

                # Reply eligibility is decided BEFORE we pause, so we can pause the
                # automation and THEN send exactly one acknowledgement (spec order:
                # create case → pause → commit → acknowledge).
                can_reply = (live and mode != "paused"
                             and convo.get("status") != "human_takeover")
                if category == "refund":
                    # A refund must NEVER be handled by the AI. Durably hand the
                    # conversation to Operations (status=human_takeover) so every
                    # LATER message is held for a human until an authorised release
                    # — not just this turn. Then send the ONE approved refund notice
                    # (never approves/promises/quotes a refund).
                    logger.info("refund_intent_detected", sender=masked,
                                order=order_ref, has_order_ref=has_order_ref)
                    await conversations_repo.start_human_takeover(convo["id"], operator_name=None)
                    logger.info("refund_human_intervention_created", sender=masked,
                                order=order_ref, reason="REFUND_REQUEST")
                    if can_reply:
                        try:
                            await EvolutionWhatsAppChannel.from_settings().send_text(
                                to_phone=sender, text=_REFUND_ACK_TEXT)
                            await messages_repo.add_message(
                                convo["id"], "agent", _REFUND_ACK_TEXT, status="sent",
                                metadata={"kind": "refund_ack",
                                          "idempotency_key": f"{convo['id']}:refund:notice"})
                            logger.info("refund_notice_sent", sender=masked)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("refund_ack_failed", sender=masked, error=str(exc))
                elif can_reply:
                    # Other complaints: one empathetic acknowledgement (no
                    # compensation promise). These are NOT durably paused here.
                    ack = complaints.empathetic_ack(
                        complaints.classify_category(text, category),
                        has_order_ref=has_order_ref, has_photo=False)
                    try:
                        await EvolutionWhatsAppChannel.from_settings().send_text(
                            to_phone=sender, text=ack)
                        await messages_repo.add_message(convo["id"], "agent", ack,
                                                        status="sent",
                                                        metadata={"kind": "complaint_ack"})
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("complaint_ack_failed", sender=masked, error=str(exc))

            # B2B enquiry → its own lead entity (NOT the consumer funnel) + a sales
            # follow-up task + a safe acknowledgement. Best-effort, never blocks.
            elif flag_type == "b2b_lead":
                try:
                    existing_lead = await b2b_leads_repo.get_open_for_conversation(convo["id"])
                    if existing_lead is None:
                        btype = b2b.classify_business_type(text)
                        lead = await b2b_leads_repo.create(
                            customer_id=customer["id"], conversation_id=convo["id"],
                            business_type=btype, market=customer.get("market"),
                            location=customer.get("area") or customer.get("city"),
                            notes=stored_text)
                        await pending_tasks_repo.create(
                            "AWAITING_OPERATIONS_RESPONSE",
                            customer_id=customer["id"], conversation_id=convo["id"],
                            notes=f"B2B lead {lead.get('lead_ref') if lead else ''} ({btype})")
                        logger.info("b2b_lead_created", sender=masked, business_type=btype,
                                    ref=(lead or {}).get("lead_ref"))
                    can_reply = (live and mode != "paused"
                                 and convo.get("status") != "human_takeover")
                    if can_reply:
                        b2b_ack = b2b.acknowledgement(b2b.classify_business_type(text))
                        try:
                            await EvolutionWhatsAppChannel.from_settings().send_text(
                                to_phone=sender, text=b2b_ack)
                            await messages_repo.add_message(convo["id"], "agent", b2b_ack,
                                                            status="sent",
                                                            metadata={"kind": "b2b_ack"})
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("b2b_ack_failed", sender=masked, error=str(exc))
                except Exception as exc:  # noqa: BLE001 - never break the handoff
                    logger.warning("b2b_lead_failed", sender=masked, error=str(exc))

            if inbound_msg:
                await messages_repo.set_status(inbound_msg["id"], "human_needed")
            # Cancel any pending buffered turn so a delayed AI reply never talks
            # over the human now handling this escalation (spec §24).
            if settings.whatsapp_message_aggregation_enabled:
                await get_turn_buffer().cancel(convo["id"])
            # Recompute CRM lifecycle/segments so complaint_open / b2b_lead is
            # reflected immediately (deterministic, best-effort — never raises).
            await crm_repo.recompute_for_customer(customer["id"])
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

        # --- AGGREGATE fragments into one turn, or process this message inline ---
        # Customers often send one thought as several quick fragments; buffer them
        # per conversation and process the combined logical turn ONCE (spec
        # §§14-23). When aggregation is off, process this single message inline
        # (the legacy per-message behaviour).
        if settings.whatsapp_message_aggregation_enabled:
            buf = get_turn_buffer()
            # ADAPTIVE debounce: classify THIS fragment locally (no LLM call) and
            # pick the inactivity wait — a complete message / structured action is
            # processed quickly; a short fragment waits longer to be combined.
            label = message_completeness.classify(
                text, selection_id=msg.get("selection_id"),
                has_location=(msg.get("latitude") is not None))
            debounce_s = message_completeness.debounce_seconds(
                label,
                short_s=settings.debounce_short_seconds,
                standard_s=settings.debounce_standard_seconds,
                fragment_s=settings.debounce_fragment_seconds)
            logger.info("message_completeness_classified", conversation=convo["id"],
                        classification=label.value)
            logger.info("adaptive_debounce_selected", conversation=convo["id"],
                        classification=label.value, debounce_ms=int(debounce_s * 1000))
            turn = await buf.add_fragment(
                convo["id"], customer.get("id"),
                message_id=(inbound_msg or {}).get("id"), message_at=_utcnow(),
                debounce_seconds=debounce_s)

            async def _processor(cid, combined, turn_row, *, _c=convo, _cust=customer,
                                 _phone=msg["phone"], _masked=masked, _live=live,
                                 _last=inbound_msg):
                await _process_reply(_c, _cust, combined, phone=_phone, masked=_masked,
                                     live=_live, last_inbound_msg=_last,
                                     turn_id=(turn_row or {}).get("turn_id"))
                return None

            # A bare interactive selection or an explicit "that's all" is a complete
            # turn — process now rather than waiting out the debounce (spec §§16/23).
            bare_selection = bool(msg.get("selection_id")) and not text.strip()
            if message_aggregation.is_explicit_send(text) or bare_selection:
                await buf.flush(convo["id"], _processor)
            else:
                buf.schedule(convo["id"], turn, _processor)
            processed += 1
            continue

        # Aggregation OFF -> handle this single message immediately (legacy path).
        single = message_aggregation.combine_fragments([{
            "text": text, "selection_id": msg.get("selection_id"),
            "latitude": msg.get("latitude"), "longitude": msg.get("longitude")}])
        await _process_reply(convo, customer, single, phone=msg["phone"],
                             masked=masked, live=live, last_inbound_msg=inbound_msg)
        processed += 1

    return {"status": "ok", "stored": True, "processed": processed,
            "skipped": skipped, "duplicates": duplicates}
