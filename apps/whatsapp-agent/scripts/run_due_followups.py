"""Send due customer follow-ups (spec §§14, 24, 25).

The scheduling POLICY is pure (services/followups + services/followup_scheduler); this
sweeper is the thin driver a scheduler (cron / Celery beat) runs periodically:

    python scripts/run_due_followups.py

For each PENDING follow-up whose time has come it builds the LIVE suppression context
(did the customer reply, pay, choose cash, confirm the order, is a human handling it),
lets the policy pick at most ONE follow-up per conversation (the most relevant), and
sends it — but ONLY through the SAME safety gates the webhook uses: never when the agent
is paused, and in test mode only to allow-listed numbers. Sent rows are marked SENT;
suppressed ones are marked SUPPRESSED (with a reason). Idempotent and safe to re-run.

Supabase-only (the queue lives there). A no-op in SQLite/local mode.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from channels.evolution_whatsapp import EvolutionWhatsAppChannel  # noqa: E402
from db import database  # noqa: E402
from db.repositories import scheduled_followups_repo as followups_repo  # noqa: E402
from services import followup_scheduler as sched  # noqa: E402
from services import followups as fu  # noqa: E402
from services.clock import now as clock_now  # noqa: E402
from services.privacy import mask_phone, normalize_e164  # noqa: E402
from services.reply_style import normalize_customer_reply  # noqa: E402
from settings import get_settings  # noqa: E402


async def _suppression_context(row: dict) -> fu.SuppressionContext:
    """Build the live suppression context for one queued follow-up from the DB."""
    conv_id = row.get("conversation_id")
    anchor = row.get("anchor_at")
    replied = human = False
    if conv_id:
        if anchor:
            r = await database.fetchrow(
                "select 1 from messages where conversation_id = $1::uuid "
                "and sender_type = 'customer' and created_at > $2 limit 1",
                conv_id, anchor)
            replied = r is not None
        c = await database.fetchrow("select status from conversations where id = $1::uuid", conv_id)
        human = bool(c and str(c.get("status") or "").lower() in ("human_takeover", "human_needed"))

    paid = cash = confirmed = False
    order_id = row.get("order_id")
    if order_id:
        o = await database.fetchrow(
            "select status, payment_preference, payment_status from orders where order_id = $1",
            order_id)
        if o:
            paid = str(o.get("payment_status") or "") == "paid"
            cash = str(o.get("payment_preference") or "") == "CASH_ON_DELIVERY"
            confirmed = str(o.get("status") or "draft") not in ("draft", "")

    # Website-abandonment rows have no conversation/order yet — suppress them once the
    # visitor's number has converted (they messaged us; the webhook marks the intent).
    converted = False
    if row["followup_type"] in ("WEB_ABANDONMENT_1", "WEB_ABANDONMENT_2", "WEB_ABANDONMENT_3"):
        from db.repositories import web_order_intents_repo
        converted = await web_order_intents_repo.is_converted_number(row.get("customer_phone") or "")

    return fu.SuppressionContext(
        customer_replied=replied, human_takeover=human,
        paid=paid, cash_selected=cash, order_confirmed=confirmed, converted=converted)


async def _handle_discount_objection(row: dict) -> tuple[str, str | None]:
    """Backend re-decision for a due DISCOUNT_OBJECTION follow-up (spec §8/§9). The AI
    never picks anything: the deterministic discount engine (via discount_followup.decide)
    says whether to SEND a backend-approved offer, raise a silent conversion REVIEW, or
    SUPPRESS. Returns (outcome, text) where text is set only for SEND."""
    from services import discount_followup, negotiation_review

    p = row.get("payload") or {}
    # Guard against re-offering a quote the customer no longer sees: compare the order
    # total captured at schedule time with the current one.
    current_total = None
    order_id = row.get("order_id")
    if order_id:
        o = await database.fetchrow("select estimated_total from orders where order_id = $1", order_id)
        current_total = float(o["estimated_total"]) if o and o.get("estimated_total") is not None else None

    decision = discount_followup.decide(
        subtotal=p.get("subtotal") or 0,
        current_percentage=p.get("current_percentage"),
        current_rule_code=p.get("current_rule_code"),
        itemised=bool(p.get("itemised")),
        facility_cost=p.get("facility_cost"),
        stored_quote_version=p.get("quote_version"),
        current_quote_version=current_total,
        currency=p.get("currency", "AED"))

    if decision.kind == discount_followup.REVIEW:
        try:
            await negotiation_review.flag_conversion_review(
                conversation_id=row.get("conversation_id"), order_id=order_id,
                reason=decision.reason or "CUSTOMER_CONVERSION_REVIEW",
                context={"current_price": p.get("subtotal"),
                         "existing_discount": p.get("current_percentage"),
                         "facility_cost": p.get("facility_cost"),
                         "hesitation": "PRICE_OBJECTION"})
        except Exception as exc:  # noqa: BLE001 - review is best-effort
            print(f"conversion_review_failed error={exc}")
        return "review", None
    if decision.kind == discount_followup.SEND:
        return "send", decision.text
    return "suppress", decision.reason


def _may_send(phone: str | None) -> bool:
    """The webhook's outbound gate: never when paused; in test mode only to the
    allow-list; otherwise (live) allowed. Sending still requires a configured provider."""
    s = get_settings()
    if not s.agent_replies_enabled:
        return False
    if s.agent_operating_mode == "test":
        return normalize_e164(phone or "") in s.allowed_auto_reply_numbers
    return True


async def run_due_followups() -> dict:
    """Send the due follow-ups. Returns a small summary (counts)."""
    settings = get_settings()
    if not database.is_supabase_mode():
        return {"skipped": "not_supabase_mode", "sent": 0}

    now = clock_now()
    due_rows = await followups_repo.load_due(now)
    if not due_rows:
        return {"due": 0, "sent": 0, "suppressed": 0}

    # Build contexts once per row, then let the policy choose one send per conversation.
    ctx_cache: dict = {}
    for r in due_rows:
        ctx_cache[r["id"]] = await _suppression_context(r)

    sent = suppressed = 0

    # DISCOUNT_OBJECTION follow-ups take a dedicated backend re-decision (send an
    # approved offer / raise a silent review / suppress) rather than the generic
    # template-render path. Handle and remove them before generic arbitration.
    handled_ids: set = set()
    generic_rows = []
    for r in due_rows:
        if r["followup_type"] != fu.DISCOUNT_OBJECTION:
            generic_rows.append(r)
            continue
        handled_ids.add(r["id"])
        supp, reason = fu.is_suppressed(fu.DISCOUNT_OBJECTION, ctx_cache[r["id"]])
        if supp:
            await followups_repo.mark_suppressed(r["id"], reason or "suppressed")
            suppressed += 1
            continue
        outcome, text = await _handle_discount_objection(r)
        if outcome == "send" and text and _may_send(r.get("customer_phone")):
            try:
                await EvolutionWhatsAppChannel.from_settings().send_text(
                    to_phone=r.get("customer_phone"), text=normalize_customer_reply(text).text)
                await followups_repo.mark_sent(r["id"])
                sent += 1
                print(f"followup_sent type=DISCOUNT_OBJECTION to={mask_phone(r.get('customer_phone'))}")
            except Exception as exc:  # noqa: BLE001 - never abort the sweep on one send
                print(f"followup_send_failed type=DISCOUNT_OBJECTION error={exc}")
        elif outcome == "review":
            await followups_repo.mark_suppressed(r["id"], "conversion_review")
            suppressed += 1
        elif outcome == "suppress":
            await followups_repo.mark_suppressed(r["id"], text or "not_eligible")
            suppressed += 1
        # outcome == "send" but not sendable now (paused / not allow-listed) → leave PENDING.

    def ctx_provider(conversation_id, followup_type):
        for r in generic_rows:
            if r.get("conversation_id") == conversation_id and r["followup_type"] == followup_type:
                return ctx_cache[r["id"]]
        return fu.SuppressionContext()

    plans = sched.plan_batch(generic_rows, ctx_provider, now)
    chosen_ids = {p.followup_id for p in plans}
    # Mark the rows the policy actively suppressed (so they don't linger as PENDING).
    for r in generic_rows:
        if r["id"] in chosen_ids:
            continue
        supp, reason = fu.is_suppressed(r["followup_type"], ctx_cache[r["id"]])
        if supp:
            await followups_repo.mark_suppressed(r["id"], reason or "suppressed")
            suppressed += 1

    for p in plans:
        if not _may_send(p.customer_phone):
            # Not sendable now (paused / not allow-listed). Leave PENDING for a later
            # sweep inside an allowed window rather than dropping it.
            continue
        text = normalize_customer_reply(p.text).text
        try:
            await EvolutionWhatsAppChannel.from_settings().send_text(
                to_phone=p.customer_phone, text=text)
            await followups_repo.mark_sent(p.followup_id)
            sent += 1
            print(f"followup_sent type={p.followup_type} to={mask_phone(p.customer_phone)}")
        except Exception as exc:  # noqa: BLE001 - never abort the sweep on one send
            print(f"followup_send_failed type={p.followup_type} error={exc}")

    return {"due": len(due_rows), "sent": sent, "suppressed": suppressed}


if __name__ == "__main__":
    print(asyncio.run(run_due_followups()))
