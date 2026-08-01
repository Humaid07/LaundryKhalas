"""Facility (laundry partner) Dashboard API.

Every endpoint is guarded by ``deps.require_facility_scope`` and reads the
resolved ``facility_id`` from the injected principal — NEVER from a client-
supplied query param. All data returned is PII-safe (CLAUDE.md §7): order views
carry area/city + customer first name only, never full phone/email/address.

Supabase-backed: outside supabase mode reads return empty/typed defaults and
writes raise 503 (mirrors api/flags.py + api/tickets.py).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from api import deps
from db import database
from db.repositories import (
    catalogue_repo,
    driver_assignments_repo,
    facilities_repo,
    facility_drivers_repo,
    facility_finance_repo,
    facility_issue_messages_repo,
    facility_issues_repo,
    facility_notifications_repo,
    facility_orders_repo,
    facility_settings_repo,
    order_events_repo,
)
from services import facility_bank
from services import facility_drivers as driver_svc
from services import facility_orders as facility_actions
from services import rating_service
from services.facility_bank import BankValidationError
from schemas import BankDetailsUpsert

router = APIRouter(prefix="/api/facility", tags=["facility"])


def _fid(principal: dict) -> str:
    fid = (principal or {}).get("facility_id")
    if not fid:
        raise HTTPException(status_code=403, detail="No facility in scope.")
    return fid


def _require_supabase_write():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Facility dashboard requires DATABASE_MODE=supabase (dev/test Supabase project).",
        )


def _require_manage(principal: dict):
    """403 unless the facility role may manage drivers / assignments (owner,
    manager, or platform admin). Enforced server-side — never trust the client."""
    if not driver_svc.can_manage((principal or {}).get("role")):
        raise HTTPException(
            status_code=403,
            detail="Your role can view drivers but cannot manage them or assign tasks.",
        )


def _range_to_dates(range_: str | None, frm: str | None, to: str | None) -> tuple[date | None, date | None]:
    """Map a range keyword → (date_from, date_to) inclusive dates. custom uses
    from/to (YYYY-MM-DD). Unknown/absent → (None, None) = all time."""
    today = datetime.utcnow().date()
    r = (range_ or "").lower()
    if r == "today":
        return today, today
    if r == "week":
        return today - timedelta(days=6), today
    if r == "month":
        return today - timedelta(days=29), today
    if r == "custom":
        def _p(v):
            try:
                return date.fromisoformat(v) if v else None
            except ValueError:
                return None
        return _p(frm), _p(to)
    return None, None


# --------------------------------------------------------------------------
# Profile / overview
# --------------------------------------------------------------------------
@router.get("/me")
async def facility_me(request: Request, principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"facility": None, "role": (principal or {}).get("role")}
    profile = await facilities_repo.get(_fid(principal))
    return {"facility": profile, "role": (principal or {}).get("role")}


@router.get("/overview")
async def facility_overview(request: Request, principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {}
    fid = _fid(principal)
    ov = await facilities_repo.overview(fid)
    issues = await facility_issues_repo.list_issues(facility_id=fid)
    latest_issue = issues[0]["status"] if issues else None
    return {**ov, "latest_issue_status": latest_issue, "metrics": await facility_orders_repo.metrics(fid)}


# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
@router.get("/orders")
async def facility_orders_list(
    request: Request,
    bucket: str = "all",
    range: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    service: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        return {"orders": [], "metrics": {}}
    fid = _fid(principal)
    frm = from_ or request.query_params.get("from")
    date_from, date_to = _range_to_dates(range, frm, to)
    orders = await facility_orders_repo.list_bucket(
        fid, bucket, date_from=date_from, date_to=date_to,
        service_id=service, status=status, limit=limit, offset=offset,
    )
    return {"orders": orders, "metrics": await facility_orders_repo.metrics(fid)}


@router.get("/orders/{order_id}")
async def facility_order_detail(
    order_id: str, request: Request, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Order not found.")
    fid = _fid(principal)
    order = await facility_orders_repo.get(fid, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found for this facility.")
    row = await facility_orders_repo.get_row(fid, order_id)
    timeline = await order_events_repo.list_for_order(str(row["id"])) if row else []
    # Related facility issues (scoped) for this order.
    issues = [i for i in await facility_issues_repo.list_issues(facility_id=fid)
              if row and i.get("order_id") and str(i["order_id"]) == str(row["id"])]
    # Active driver assignment (PII-safe) for the order-detail driver panel.
    assignment = await driver_assignments_repo.active_for_order(fid, str(row["id"])) if row else None
    driver = None
    if assignment and assignment.get("driver_id"):
        driver = await facility_drivers_repo.get(fid, assignment["driver_id"])

    # Additional order notes (grouped) + config-gated typed address / location pin,
    # via the centralized facility-handoff serializer (privacy firewall). Best-effort.
    additional_notes: dict = {}
    handoff_extra: dict = {}
    if row:
        try:
            from db.repositories import order_notes_repo
            from services import facility_handoff, order_notes as _notes_mod
            from settings import get_settings
            active = await order_notes_repo.list_active(str(row["id"]))
            additional_notes = _notes_mod.group_active_by_category(active)
            share = facility_handoff.config_from_settings(get_settings())
            payload = facility_handoff.build_facility_handoff_payload(
                order=dict(row), active_notes=active, customer=None, share=share)
            handoff_extra = {
                "grouped_notes": payload.get("notes", {}),
                "pickup_address_full": payload.get("pickup_address"),
                "location_pin": payload.get("location_pin"),
                "location_pin_status": payload.get("location_pin_status"),
            }
        except Exception:  # noqa: BLE001 — notes/address are additive to the detail
            pass

    return {**order, "timeline": timeline, "related_issues": issues,
            "driver_assignment": assignment, "driver": driver,
            "additional_notes": additional_notes, **handoff_extra}


@router.patch("/orders/{order_id}/status")
async def facility_order_action(
    order_id: str,
    body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    action = (body or {}).get("action")
    if not action:
        raise HTTPException(status_code=400, detail="An 'action' is required.")
    actor_label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    try:
        return await facility_actions.apply_action(fid, order_id, action, actor_label=actor_label)
    except facility_actions.ForbiddenFacilityAction as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except facility_actions.InvalidFacilityAction as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Order not found for this facility.")


@router.post("/orders/{order_id}/notes")
async def facility_order_note(
    order_id: str,
    body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    note = (body or {}).get("note")
    if not note:
        raise HTTPException(status_code=400, detail="A 'note' is required.")
    row = await facility_orders_repo.get_row(fid, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found for this facility.")
    actor_label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    event = await order_events_repo.create(
        order_uuid=str(row["id"]), event_type="facility_note",
        actor_type="facility", actor_name=actor_label, notes=note,
    )
    return event or {}


@router.post("/orders/{order_id}/issues")
async def facility_order_issue(
    order_id: str,
    body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    issue_type = (body or {}).get("issue_type")
    message = (body or {}).get("message")
    if not issue_type or not message:
        raise HTTPException(status_code=400, detail="'issue_type' and 'message' are required.")
    row = await facility_orders_repo.get_row(fid, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found for this facility.")
    label = (principal or {}).get("full_name") or "Facility"
    return await facility_issues_repo.create(
        facility_id=fid, issue_type=issue_type, message=message,
        title=(body or {}).get("title"),
        severity=(body or {}).get("severity", "medium"),
        priority=(body or {}).get("priority", "normal"),
        order_uuid=str(row["id"]), order_ref=row.get("order_id"),
        created_by_user_id=(principal or {}).get("id"), created_by_label=label,
    )


# --------------------------------------------------------------------------
# Finance
# --------------------------------------------------------------------------
def _finance_dates(range_, frm, to):
    date_from, date_to = _range_to_dates(range_, frm, to)
    # finance repo uses `< date_to`, so make the upper bound exclusive+inclusive.
    date_to_excl = (date_to + timedelta(days=1)) if date_to else None
    return date_from, date_to_excl


@router.get("/finance/summary")
async def facility_finance_summary(
    request: Request, range: str | None = None, from_: str | None = None,
    to: str | None = None, principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        return {}
    frm = from_ or request.query_params.get("from")
    date_from, date_to = _finance_dates(range, frm, to)
    return await facility_finance_repo.summary(_fid(principal), date_from, date_to)


@router.get("/finance/revenue")
async def facility_finance_revenue(
    request: Request, granularity: str = "day", range: str | None = None,
    from_: str | None = None, to: str | None = None,
    principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        return {"granularity": granularity, "series": []}
    frm = from_ or request.query_params.get("from")
    date_from, date_to = _finance_dates(range, frm, to)
    series = await facility_finance_repo.revenue_timeseries(
        _fid(principal), granularity, date_from, date_to)
    return {"granularity": granularity, "series": series}


@router.get("/finance/services")
async def facility_finance_services(
    request: Request, range: str | None = None, from_: str | None = None,
    to: str | None = None, principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        return {"services": []}
    frm = from_ or request.query_params.get("from")
    date_from, date_to = _finance_dates(range, frm, to)
    return {"services": await facility_finance_repo.service_mix(_fid(principal), date_from, date_to)}


@router.get("/finance/payouts")
async def facility_finance_payouts(principal: dict = Depends(deps.require_facility_scope)):
    # Partner payout rate is deferred — reported pending, never invented.
    return {
        "payout_status": "pending_rate",
        "payout_amount": None,
        "currency": "AED",
        "note": "Partner payout rate is not configured yet. Completed service value "
                "is shown under Finance; payout will appear once rates are set.",
    }


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
@router.get("/settings/profile")
async def get_settings_profile(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return None
    return await facilities_repo.get(_fid(principal))


@router.patch("/settings/profile")
async def patch_settings_profile(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    fid = _fid(principal)
    # Only a small set of non-sensitive profile fields are editable by a facility.
    allowed = {k: v for k, v in (body or {}).items()
               if k in {"operating_status", "notes", "contact_area"}}
    if not allowed:
        return await facilities_repo.get(fid)
    sets, params = [], [fid]
    for col, val in allowed.items():
        params.append(val)
        sets.append(f"{col} = ${len(params)}")
    await database.execute(
        f"update facilities set {', '.join(sets)} where id = $1", *params
    )
    return await facilities_repo.get(fid)


@router.get("/settings/operations")
async def get_settings_operations(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return None
    return await facility_settings_repo.get_settings(_fid(principal))


@router.patch("/settings/operations")
async def patch_settings_operations(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    return await facility_settings_repo.update_settings(_fid(principal), **(body or {}))


# --- bank details (payout banking) -----------------------------------------
# Scoped to the caller's own facility (facility_id from the session). Reads return
# MASKED values only; the full IBAN/account number are exposed solely via the
# explicit reveal action, which is limited to owner/manager and audited.
@router.get("/bank-details")
async def get_bank_details(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return None
    return await facility_bank.get_masked(_fid(principal))


@router.put("/bank-details")
async def put_bank_details(
    body: BankDetailsUpsert, principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    _require_manage(principal)  # owner/manager only — staff cannot edit banking
    try:
        return await facility_bank.upsert(
            _fid(principal), body.model_dump(exclude_unset=True),
            actor_id=(principal or {}).get("id"), actor_type="partner",
            source_app="partner_portal",
        )
    except BankValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/bank-details/reveal")
async def reveal_bank_details(principal: dict = Depends(deps.require_facility_scope)):
    _require_supabase_write()
    _require_manage(principal)  # explicit reveal is owner/manager only + audited
    revealed = await facility_bank.reveal(
        _fid(principal), actor_id=(principal or {}).get("id"),
        actor_type="partner", source_app="partner_portal",
    )
    if revealed is None:
        raise HTTPException(status_code=404, detail="No bank details on file.")
    return revealed


@router.get("/settings/timings")
async def get_settings_timings(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"timings": []}
    return {"timings": await facility_settings_repo.list_timings(_fid(principal))}


@router.patch("/settings/timings")
async def patch_settings_timings(
    body=Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    fid = _fid(principal)
    rows = body if isinstance(body, list) else (body or {}).get("timings", [])
    out = []
    for r in rows:
        dow = r.get("day_of_week")
        if dow is None:
            continue
        out.append(await facility_settings_repo.upsert_timing(
            fid, int(dow),
            opens_at=r.get("opens_at"), closes_at=r.get("closes_at"),
            receiving_start=r.get("receiving_start"), receiving_end=r.get("receiving_end"),
            handoff_start=r.get("handoff_start"), handoff_end=r.get("handoff_end"),
            same_day_cutoff=r.get("same_day_cutoff"), is_closed=r.get("is_closed", False),
            is_24h=r.get("is_24h", False),
        ))
    return {"timings": out}


@router.get("/service-categories")
async def get_service_categories(principal: dict = Depends(deps.require_facility_scope)):
    """The catalogue service categories a facility can offer (for the accepted-
    services picker). Categories are non-sensitive published service types."""
    if not database.is_supabase_mode():
        return {"categories": []}
    return {"categories": await catalogue_repo.list_categories()}


@router.get("/settings/prices")
async def get_settings_prices(principal: dict = Depends(deps.require_facility_scope)):
    return await facility_settings_repo.get_prices(_fid(principal))


@router.post("/settings/prices/change-request")
async def post_price_change_request(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    return await facility_settings_repo.create_price_request(
        _fid(principal),
        item_code=(body or {}).get("item_code"),
        item_label=(body or {}).get("item_label"),
        unit_type=(body or {}).get("unit_type"),
        current_price=(body or {}).get("current_price"),
        requested_price=(body or {}).get("requested_price"),
        reason=(body or {}).get("reason"),
        requested_by_user_id=(principal or {}).get("id"),
    )


@router.get("/settings/team")
async def get_settings_team(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"team": []}
    return {"team": await facility_settings_repo.list_team(_fid(principal))}


@router.post("/settings/team")
async def post_settings_team(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    if not (body or {}).get("name"):
        raise HTTPException(status_code=400, detail="A team member 'name' is required.")
    return await facility_settings_repo.add_member(
        _fid(principal), name=body["name"], role=body.get("role", "facility_staff"),
        phone_e164=body.get("phone_e164"), vehicle_type=body.get("vehicle_type"),
        responsibilities=body.get("responsibilities"), status=body.get("status", "active"),
    )


@router.patch("/settings/team/{member_id}")
async def patch_settings_team(
    member_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    updated = await facility_settings_repo.update_member(
        _fid(principal), member_id,
        name=(body or {}).get("name"), role=(body or {}).get("role"),
        phone_e164=(body or {}).get("phone_e164"), vehicle_type=(body or {}).get("vehicle_type"),
        responsibilities=(body or {}).get("responsibilities"), status=(body or {}).get("status"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Team member not found.")
    return updated


@router.get("/settings/notifications")
async def get_settings_notifications(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"contacts": []}
    return {"contacts": await facility_notifications_repo.list_contacts(_fid(principal))}


@router.post("/settings/notifications")
async def post_settings_notifications(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    if not (body or {}).get("name") or not (body or {}).get("mobile_e164"):
        raise HTTPException(status_code=400, detail="'name' and 'mobile_e164' are required.")
    return await facility_notifications_repo.add_contact(
        _fid(principal), name=body["name"], mobile_e164=body["mobile_e164"],
        role=body.get("role"), notification_types=body.get("notification_types"),
        active=body.get("active", True),
    )


@router.patch("/settings/notifications/{contact_id}")
async def patch_settings_notifications(
    contact_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    updated = await facility_notifications_repo.update_contact(
        _fid(principal), contact_id,
        name=(body or {}).get("name"), role=(body or {}).get("role"),
        mobile_e164=(body or {}).get("mobile_e164"),
        notification_types=(body or {}).get("notification_types"),
        active=(body or {}).get("active"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return updated


# --------------------------------------------------------------------------
# Issues (facility side — internal-only notes are hidden)
# --------------------------------------------------------------------------
@router.get("/issues")
async def facility_issues_list(
    status: str | None = None, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        return []
    return await facility_issues_repo.list_issues(facility_id=_fid(principal), status=status)


@router.get("/issues/{issue_id}")
async def facility_issue_detail(
    issue_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Issue not found.")
    issue = await facility_issues_repo.get(issue_id, facility_id=_fid(principal))
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found for this facility.")
    return issue


@router.post("/issues")
async def facility_issue_create(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    fid = _fid(principal)
    issue_type = (body or {}).get("issue_type")
    message = (body or {}).get("message")
    if not issue_type or not message:
        raise HTTPException(status_code=400, detail="'issue_type' and 'message' are required.")
    label = (principal or {}).get("full_name") or "Facility"
    order_ref = (body or {}).get("order_ref")
    order_uuid = None
    if order_ref:
        row = await facility_orders_repo.get_row(fid, order_ref)
        if row is not None:
            order_uuid, order_ref = str(row["id"]), row.get("order_id")
    return await facility_issues_repo.create(
        facility_id=fid, issue_type=issue_type, message=message,
        title=(body or {}).get("title"),
        severity=(body or {}).get("severity", "medium"),
        priority=(body or {}).get("priority", "normal"),
        order_uuid=order_uuid, order_ref=order_ref,
        requested_help=(body or {}).get("requested_help"),
        created_by_user_id=(principal or {}).get("id"), created_by_label=label,
    )


@router.get("/issues/{issue_id}/messages")
async def facility_issue_messages(
    issue_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        return []
    issue = await facility_issues_repo.get(issue_id, facility_id=_fid(principal))
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found for this facility.")
    # Facility side never sees internal-only notes.
    return await facility_issue_messages_repo.list_messages(issue_id, include_internal=False)


@router.post("/issues/{issue_id}/messages")
async def facility_issue_reply(
    issue_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    message = (body or {}).get("message")
    if not message:
        raise HTTPException(status_code=400, detail="A 'message' is required.")
    issue = await facility_issues_repo.get(issue_id, facility_id=fid)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found for this facility.")
    label = (principal or {}).get("full_name") or "Facility"
    msg = await facility_issue_messages_repo.add_message(
        issue_id, "facility", message, sender_id=(principal or {}).get("id"),
        sender_label=label, is_internal=False,
    )
    # A facility reply moves the ball to the internal team.
    await facility_issues_repo.set_status(issue_id, "waiting_on_internal_team")
    return msg or {}


@router.post("/issues/{issue_id}/resolve")
async def facility_issue_resolve(
    issue_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    issue = await facility_issues_repo.get(issue_id, facility_id=_fid(principal))
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found for this facility.")
    return await facility_issues_repo.resolve(issue_id)


# --------------------------------------------------------------------------
# Drivers (operational driver status + order-task assignment)
# --------------------------------------------------------------------------
@router.get("/drivers")
async def facility_drivers_list(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"drivers": [], "summary": {}}
    return await driver_svc.list_with_status(_fid(principal))


@router.get("/drivers/summary")
async def facility_drivers_summary(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {}
    return (await driver_svc.list_with_status(_fid(principal))).get("summary", {})


@router.get("/drivers/{driver_id}")
async def facility_driver_detail(
    driver_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Driver not found.")
    fid = _fid(principal)
    driver = await driver_svc.get_with_status(fid, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found for this facility.")
    assignments = await driver_assignments_repo.list_for_driver(fid, driver_id)
    return {**driver, "assignments": assignments}


@router.get("/drivers/{driver_id}/assignments")
async def facility_driver_assignments(
    driver_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        return {"assignments": []}
    fid = _fid(principal)
    if await facility_drivers_repo.get(fid, driver_id) is None:
        raise HTTPException(status_code=404, detail="Driver not found for this facility.")
    return {"assignments": await driver_assignments_repo.list_for_driver(fid, driver_id)}


# --- ratings (READ-ONLY for partners) --------------------------------------
# A partner sees only its OWN facility rating and the ratings of drivers assigned
# to its facility. Everything is partner-shaped (no internal notes / drafts /
# evaluator identity); partners can never create or edit ratings.
@router.get("/rating")
async def facility_rating(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"summary": {"overall_score": None, "evaluation_count": 0,
                            "latest_evaluation_date": None, "factor_averages": [], "trend": []},
                "latest": None}
    return await rating_service.facility_partner_view(_fid(principal))


@router.get("/ratings/drivers")
async def facility_driver_ratings(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"drivers": []}
    fid = _fid(principal)
    drivers = (await driver_svc.list_with_status(fid)).get("drivers", [])
    out = []
    for d in drivers:
        view = await rating_service.driver_partner_view(str(d["id"]))
        out.append({
            "driver_id": str(d["id"]),
            "name": d.get("name"),
            "role": d.get("role"),
            "summary": view["summary"],
            "latest": view["latest"],
        })
    return {"drivers": out}


@router.get("/drivers/{driver_id}/rating")
async def facility_driver_rating(
    driver_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        return {"summary": {"overall_score": None, "evaluation_count": 0,
                            "latest_evaluation_date": None, "factor_averages": [], "trend": []},
                "latest": None}
    fid = _fid(principal)
    # Ownership: the driver must belong to THIS facility, else it's not visible.
    if await facility_drivers_repo.get(fid, driver_id) is None:
        raise HTTPException(status_code=404, detail="Driver not found for this facility.")
    return await rating_service.driver_partner_view(driver_id)


@router.post("/drivers")
async def facility_driver_create(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    _require_manage(principal)
    if not (body or {}).get("name"):
        raise HTTPException(status_code=400, detail="A driver 'name' is required.")
    return await facility_drivers_repo.create(
        _fid(principal), name=body["name"], phone_e164=body.get("phone_e164"),
        role=body.get("role", "driver"), vehicle_type=body.get("vehicle_type"),
        area=body.get("area"), active=body.get("active", True),
    )


@router.patch("/drivers/{driver_id}")
async def facility_driver_update(
    driver_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    _require_manage(principal)
    updated = await facility_drivers_repo.update(
        _fid(principal), driver_id,
        name=(body or {}).get("name"), role=(body or {}).get("role"),
        phone_e164=(body or {}).get("phone_e164"), vehicle_type=(body or {}).get("vehicle_type"),
        area=(body or {}).get("area"), active=(body or {}).get("active"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Driver not found for this facility.")
    return updated


@router.patch("/drivers/{driver_id}/status")
async def facility_driver_set_status(
    driver_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    _require_manage(principal)
    status = (body or {}).get("status")
    if not status:
        raise HTTPException(status_code=400, detail="A 'status' is required.")
    label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    try:
        return await driver_svc.set_driver_status(
            _fid(principal), driver_id, status, actor_label=label, note=(body or {}).get("note"))
    except driver_svc.DriverActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Driver not found for this facility.")


@router.post("/driver-assignments")
async def facility_driver_assignment_create(
    body: dict = Body(...), principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    _require_manage(principal)
    driver_id = (body or {}).get("driver_id")
    order_id = (body or {}).get("order_id") or (body or {}).get("order_ref")
    if not driver_id or not order_id:
        raise HTTPException(status_code=400, detail="'driver_id' and 'order_id' are required.")
    label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    try:
        return await driver_svc.assign_order_to_driver(
            _fid(principal), driver_id, order_id,
            task_type=(body or {}).get("task_type", "facility_handoff"),
            actor_label=label,
            expected_completion_at=(body or {}).get("expected_completion_at"),
            notes=(body or {}).get("notes"),
        )
    except driver_svc.DriverActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/driver-assignments/{assignment_id}/status")
async def facility_driver_assignment_status(
    assignment_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    _require_manage(principal)
    status = (body or {}).get("status")
    if not status:
        raise HTTPException(status_code=400, detail="A 'status' is required.")
    label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    try:
        return await driver_svc.update_assignment_status(
            _fid(principal), assignment_id, status, actor_label=label)
    except driver_svc.DriverActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Assignment not found for this facility.")


@router.post("/orders/{order_id}/assign-driver")
async def facility_order_assign_driver(
    order_id: str, body: dict = Body(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    _require_manage(principal)
    driver_id = (body or {}).get("driver_id")
    if not driver_id:
        raise HTTPException(status_code=400, detail="A 'driver_id' is required.")
    label = (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"
    try:
        return await driver_svc.assign_order_to_driver(
            _fid(principal), driver_id, order_id,
            task_type=(body or {}).get("task_type", "facility_handoff"),
            actor_label=label,
            expected_completion_at=(body or {}).get("expected_completion_at"),
            notes=(body or {}).get("notes"),
        )
    except driver_svc.DriverActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@router.get("/notifications")
async def facility_notifications_list(
    unread_only: bool = False, principal: dict = Depends(deps.require_facility_scope)
):
    if not database.is_supabase_mode():
        return {"notifications": [], "unread": 0}
    fid = _fid(principal)
    return {
        "notifications": await facility_notifications_repo.list_for_facility(
            fid, unread_only=unread_only),
        "unread": await facility_notifications_repo.unread_count(fid),
    }


@router.post("/notifications/{notification_id}/read")
async def facility_notification_read(
    notification_id: str, principal: dict = Depends(deps.require_facility_scope)
):
    _require_supabase_write()
    updated = await facility_notifications_repo.mark_read(_fid(principal), notification_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Notification not found or already read.")
    return updated


@router.get("/notifications/unread-count")
async def facility_notifications_unread(principal: dict = Depends(deps.require_facility_scope)):
    if not database.is_supabase_mode():
        return {"unread": 0}
    return {"unread": await facility_notifications_repo.unread_count(_fid(principal))}
