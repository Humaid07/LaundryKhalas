"""First-confirm side effects for an order — shared by BOTH confirm paths.

An order can be confirmed two ways:
  1. the deterministic booking FSM (``booking_flow`` → ``evolution_webhooks``), and
  2. the Claude (Anthropic) natural-language ``confirm_order`` tool
     (``agents/whatsapp_agent/booking_tools``).

The operational side effects that must fire EXACTLY ONCE on a first-time confirm
(auto-assign a facility + notify it, last-touch campaign attribution, CRM
recompute) previously lived only in the FSM branch, so orders confirmed through
the Claude path never reached a facility. This module centralises those effects
so both paths behave identically.

Every step is idempotent and best-effort: a failure here must NEVER break the
customer's confirmation reply (spec §§ risky-action / privacy — a downstream
notification or attribution problem is not the customer's problem). Callers only
run this when ``created_now`` is True (first confirm), so effects don't repeat on
duplicate confirms.
"""
from __future__ import annotations

import json

import structlog

from db import database
from db.repositories import campaigns_repo, crm_repo, facility_orders_repo, order_notes_repo
from services import facility_handoff, facility_notifications, facility_routing
from settings import get_settings

logger = structlog.get_logger()


async def _customer_for_handoff(customer_id) -> dict | None:
    if not customer_id:
        return None
    try:
        row = await database.fetchrow(
            "select customer_name, display_name, normalized_contact_number, phone_e164 "
            "from customers where id = $1",
            customer_id,
        )
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        return None


async def _confirm_notes_snapshot(order_row: dict) -> list[dict]:
    """Freeze the ACTIVE notes into the order's immutable confirmed snapshot."""
    order_uuid = str(order_row["id"])
    try:
        snapshot = await order_notes_repo.confirm_active(order_uuid)
        await database.execute(
            "update orders set confirmed_notes_snapshot = $1::jsonb, notes_confirmed_at = now(), "
            "updated_at = now() where id = $2",
            json.dumps(snapshot), order_uuid,
        )
        return snapshot
    except Exception as exc:  # noqa: BLE001
        logger.warning("confirm_notes_snapshot_failed", order=order_row.get("order_id"), error=str(exc))
        return []


async def _persist_facility_handoff(order_row: dict, customer_id, facility_id: str | None) -> None:
    """Build the sanitized facility-handoff payload (config-gated) and persist its
    status + a redacted copy for audit/history. Never raises."""
    order_uuid = str(order_row["id"])
    try:
        active_notes = await order_notes_repo.list_active(order_uuid)
        customer = await _customer_for_handoff(customer_id)
        share = facility_handoff.config_from_settings(get_settings())
        payload = facility_handoff.build_facility_handoff_payload(
            order=dict(order_row), active_notes=active_notes, customer=customer, share=share,
        )
        status = "sent" if facility_id else "pending"
        await database.execute(
            "update orders set facility_handoff_status = $1, facility_handoff_at = now(), "
            "facility_handoff_attempts = coalesce(facility_handoff_attempts,0) + 1, "
            "facility_handoff_payload = $2::jsonb, updated_at = now() where id = $3",
            status, json.dumps(payload, default=str), order_uuid,
        )
        await database.execute(
            "insert into order_events (order_id, event_type, actor_type, metadata) "
            "values ($1, $2, 'system', $3::jsonb)",
            order_uuid, "facility_handoff_sent" if facility_id else "facility_handoff_created",
            json.dumps({"facility_id": facility_id, "note_sections": list(payload.get("notes", {}).keys())}),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("facility_handoff_persist_failed", order=order_row.get("order_id"), error=str(exc))


async def apply_post_confirmation_effects(order_row: dict, customer_id) -> str | None:
    """Run the first-confirm side effects for ``order_row`` and return the
    assigned ``facility_id`` (str) or None. Never raises.

    1. Auto-assign a partner facility by pickup location + current load.
    2. Mock-notify that facility of the newly-assigned order (PII-safe).
    3. Last-touch campaign attribution for the customer's booking.
    4. Recompute the customer's CRM lifecycle stage / segments.
    """
    order_id_log = order_row.get("order_id")
    facility_id: str | None = None

    # 0. Freeze the confirmed-notes snapshot onto the order (immutable record).
    await _confirm_notes_snapshot(order_row)

    try:
        facility_id = await facility_routing.assign_facility_for_order(dict(order_row))
        if facility_id:
            order_read = facility_orders_repo.to_facility_read(dict(order_row))
            order_read["id"] = str(order_row["id"])
            await facility_notifications.notify_new_order_assigned(facility_id, order_read)
    except Exception as exc:  # noqa: BLE001 — never break the confirmation reply
        logger.warning("post_confirm_facility_failed", order=order_id_log, error=str(exc))

    # 2b. Build + persist the centralized, config-gated facility-handoff payload
    #     (confirmed notes + location + typed address + allowed customer fields).
    await _persist_facility_handoff(order_row, customer_id, facility_id)

    if customer_id:
        try:
            await campaigns_repo.attribute_booking(customer_id, str(order_row["id"]))
        except Exception as exc:  # noqa: BLE001
            logger.warning("campaign_attribution_failed", order=order_id_log, error=str(exc))
        try:
            await crm_repo.recompute_for_customer(customer_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("crm_recompute_failed", order=order_id_log, error=str(exc))

    return facility_id
