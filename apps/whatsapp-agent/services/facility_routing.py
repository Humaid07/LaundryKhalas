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
from services.routing import config as routing_config
from settings import get_settings

logger = structlog.get_logger()


def _location(order_row: dict) -> tuple[str | None, str | None, str | None]:
    area = order_row.get("pickup_area") or order_row.get("area")
    city = order_row.get("city")
    emirate = order_row.get("pickup_emirate") or order_row.get("emirate")
    return area, city, emirate


async def assign_facility_for_order(order_row: dict) -> str | None:
    """Pick + attach a facility for a newly-confirmed order. Returns the assigned
    facility_id (str) or None when nothing was assigned. Never raises.

    Dispatches to the ADVANCED shared engine when enabled (shadow/canary/live),
    else the legacy router. Production defaults keep the legacy behaviour exactly.
    """
    order_uuid = order_row.get("id")
    if not order_uuid:
        return None
    existing = order_row.get("facility_id")
    if existing:
        return str(existing)  # already assigned — never re-route (idempotent)

    settings = get_settings()
    is_test = bool(order_row.get("is_test_data"))
    if routing_config.should_run_advanced(settings, is_test=is_test):
        try:
            return await _assign_advanced(order_row, settings, is_test=is_test)
        except Exception as exc:  # noqa: BLE001 — never break booking on a routing error
            logger.warning("advanced_routing_error", order=order_row.get("order_id"), error=str(exc))
            # Safe fallback to legacy for PRODUCTION only (test orders never touch
            # legacy / real facilities). A correct "no eligible" is NOT an error and
            # does not reach here (it returns cleanly inside _assign_advanced).
            if routing_config.fallback_enabled(settings) and not is_test:
                return await _assign_legacy(order_row, fallback_used=True)
            return None
    return await _assign_legacy(order_row)


async def _assign_legacy(order_row: dict, *, fallback_used: bool = False) -> str | None:
    """The original location-ranked auto-assignment. Idempotent + never raises."""
    try:
        order_uuid = order_row.get("id")
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
                      "match_basis": match_basis,
                      "routing_engine": "legacy",
                      "fallback_used": fallback_used},
        )
        logger.info("facility_assigned", order=order_row.get("order_id"),
                    facility=facility.get("code"), match_basis=match_basis,
                    fallback_used=fallback_used)
        return facility_id
    except Exception as exc:  # noqa: BLE001 - routing must never break booking
        logger.warning("facility_assign_error",
                       order=order_row.get("order_id"), error=str(exc))
        return None


async def _record_decision(order_row, bundle, *, mode, legacy_selected=None,
                           advanced_selected=None, matched=None, fallback_used=False):
    """Persist the routing-decision snapshot (best-effort; never breaks routing)."""
    try:
        from db.repositories import routing_decisions_repo
        await routing_decisions_repo.create(
            order_uuid=str(order_row.get("id")), order_ref=order_row.get("order_id"),
            environment=("TEST" if bundle["is_test"] else "production"),
            routing_mode=mode, routing_version=bundle["routing_version"],
            result=bundle["result"], request=bundle["request"], simulation_time=bundle["when"],
            legacy_selected_facility_id=legacy_selected,
            advanced_selected_facility_id=advanced_selected,
            selections_matched=matched, fallback_used=fallback_used,
            created_by="facility_router", is_test_data=bundle["is_test"],
        )
    except Exception as exc:  # noqa: BLE001 — snapshot is diagnostic, not on the critical path
        logger.warning("routing_snapshot_error", order=order_row.get("order_id"), error=str(exc))


async def _assign_advanced(order_row: dict, settings, *, is_test: bool) -> str | None:
    """Advanced-engine assignment with mode dispatch.

    - shadow (prod): legacy still assigns; the advanced selection is evaluated and
      stored alongside for Operations to compare — assignment is NOT changed.
    - canary/live/test (authoritative): the advanced selection assigns the order
      atomically. A correct "no eligible facility" opens an Operations manual case
      and NEVER falls back to legacy (which would bypass the safety checks).
    """
    from services.routing import engine as routing_engine

    order_uuid = str(order_row.get("id"))
    bundle = await routing_engine.route_order(order_row)
    result = bundle["result"]
    advanced_selected = result.get("selected_facility_id")
    authoritative = routing_config.advanced_is_authoritative(
        settings, is_test=is_test, order_id=order_uuid)

    if not authoritative:
        # SHADOW (production): compare, store, but let legacy assign.
        area, city, emirate = _location(order_row)
        legacy_fac = await facilities_repo.select_for_location(area, city, emirate)
        legacy_selected = str(legacy_fac["id"]) if legacy_fac else None
        matched = (legacy_selected == advanced_selected)
        assigned = await _assign_legacy(order_row)
        await _record_decision(order_row, bundle, mode="shadow",
                               legacy_selected=assigned or legacy_selected,
                               advanced_selected=advanced_selected, matched=matched)
        return assigned

    mode = "test" if is_test else routing_config.resolve_mode(settings)
    if advanced_selected:
        updated = await orders_repo.set_facility(order_uuid, advanced_selected)  # atomic CAS
        if updated is None:
            logger.info("advanced_assign_skipped", order=order_row.get("order_id"),
                        reason="already_assigned")
            return None
        await order_events_repo.create(
            order_uuid=order_uuid, event_type="facility_assigned", actor_type="system",
            actor_name="Advanced Router",
            notes=result.get("selection_reason"),
            metadata={"facility_id": advanced_selected, "routing_engine": "advanced",
                      "routing_version": bundle["routing_version"], "routing_mode": mode,
                      "selected_driver_id": result.get("selected_driver_id"),
                      "selected_pickup_slot_id": result.get("selected_pickup_slot_id"),
                      "fallback_used": False},
        )
        await _record_decision(order_row, bundle, mode=mode,
                               advanced_selected=advanced_selected)
        return advanced_selected

    # No eligible facility — Operations manual-routing case (no legacy bypass).
    await order_events_repo.create(
        order_uuid=order_uuid, event_type="routing_manual_required", actor_type="system",
        actor_name="Advanced Router",
        notes="No eligible facility — routed to Operations for manual assignment.",
        metadata={"routing_engine": "advanced", "routing_mode": mode,
                  "rejected_count": result.get("rejected_count")},
    )
    await _record_decision(order_row, bundle, mode=mode, advanced_selected=None)
    return None
