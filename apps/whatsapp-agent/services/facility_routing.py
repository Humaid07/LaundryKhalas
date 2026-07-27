"""Facility routing — auto-assign a partner facility to a newly-confirmed order.

When a customer confirms a WhatsApp booking, the order is created with no
facility (``orders.facility_id`` is null). This service picks the best available
facility for the order's pickup location (see ``facilities_repo.select_for_location``),
attaches it once, and writes a ``facility_assigned`` audit event. It is the hook
that feeds work into the Facility Dashboard.

Guarantees:
- Idempotent — an already-assigned order is never re-routed (the DB update is
  guarded by ``facility_id is null``); reassignment is an ops-only action
  (CLAUDE.md §6).
- Never raises into the caller — a routing failure must not break the customer's
  booking confirmation. Any error is logged and the order is simply left
  unassigned for ops.
- No invented data — the facility is chosen purely from DB config; if no active
  facility can take work, the order stays unassigned rather than force-routed.
"""
from __future__ import annotations

import structlog

from db.repositories import facilities_repo, order_events_repo, orders_repo

logger = structlog.get_logger()


def _location(order_row: dict) -> tuple[str | None, str | None, str | None]:
    area = order_row.get("pickup_area") or order_row.get("area")
    city = order_row.get("city")
    emirate = order_row.get("pickup_emirate") or order_row.get("emirate")
    return area, city, emirate


async def assign_facility_for_order(order_row: dict) -> str | None:
    """Pick + attach a facility for a newly-confirmed order. Returns the assigned
    facility_id (str) or None when nothing was assigned (already assigned, no
    location, no available facility, or an error). Never raises."""
    try:
        order_uuid = order_row.get("id")
        if not order_uuid:
            return None

        # Already assigned (e.g. redelivered confirm) — do not re-route.
        existing = order_row.get("facility_id")
        if existing:
            return str(existing)

        area, city, emirate = _location(order_row)
        facility = await facilities_repo.select_for_location(area, city, emirate)
        if not facility:
            logger.info("facility_assign_no_candidate",
                        order=order_row.get("order_id"), area=area, city=city)
            return None

        facility_id = str(facility["id"])
        updated = await orders_repo.set_facility(str(order_uuid), facility_id)
        if updated is None:
            # Lost a race / already assigned between select and update.
            logger.info("facility_assign_skipped",
                        order=order_row.get("order_id"), reason="already_assigned")
            return None

        match_basis = facility.get("match_basis") or "fallback"
        await order_events_repo.create(
            order_uuid=str(order_uuid),
            event_type="facility_assigned",
            actor_type="system",
            actor_name="Facility Router",
            notes=(f"Auto-assigned to {facility.get('name') or facility.get('code')} "
                   f"({match_basis} match)."),
            metadata={"facility_id": facility_id,
                      "facility_code": facility.get("code"),
                      "match_basis": match_basis},
        )
        logger.info("facility_assigned", order=order_row.get("order_id"),
                    facility=facility.get("code"), match_basis=match_basis)
        return facility_id
    except Exception as exc:  # noqa: BLE001 - routing must never break booking
        logger.warning("facility_assign_error",
                       order=order_row.get("order_id"), error=str(exc))
        return None
