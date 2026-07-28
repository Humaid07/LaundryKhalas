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

import structlog

from db.repositories import campaigns_repo, crm_repo, facility_orders_repo
from services import facility_notifications, facility_routing

logger = structlog.get_logger()


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
    try:
        facility_id = await facility_routing.assign_facility_for_order(dict(order_row))
        if facility_id:
            order_read = facility_orders_repo.to_facility_read(dict(order_row))
            order_read["id"] = str(order_row["id"])
            await facility_notifications.notify_new_order_assigned(facility_id, order_read)
    except Exception as exc:  # noqa: BLE001 — never break the confirmation reply
        logger.warning("post_confirm_facility_failed", order=order_id_log, error=str(exc))

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
