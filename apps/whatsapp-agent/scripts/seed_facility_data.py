"""Seed demo facility data for the Facility (partner) Dashboard.

Idempotent + guarded by ALLOW_TEST_SEED. Creates, for the seeded facilities:
  * a facility_owner login (so the mobile app can be logged into),
  * default facility_settings + weekly facility_timings,
  * a notification contact + a couple of team members,
  * one demo facility_issue with an opening + internal reply message.

Customer PII is never stored here — only facility-side operational data.

Run:  python -m scripts.seed_facility_data        (from apps/whatsapp-agent)
"""
from __future__ import annotations

import asyncio

from db import database
from db.repositories import users_repo
from services.auth import hash_password
from services.privacy import mask_phone
from settings import get_settings

# Demo facility-owner login (dev/test only).
OWNER_EMAIL = "owner@marina.lk.test"
OWNER_PASSWORD = "Facility#2026"

_DEFAULT_HOURS = {  # day_of_week 0=Sun..6=Sat
    "opens_at": "08:00", "closes_at": "22:00",
    "receiving_start": "08:00", "receiving_end": "18:00",
    "handoff_start": "10:00", "handoff_end": "21:00",
    "same_day_cutoff": "12:00",
}


async def _facility_id(code: str) -> str | None:
    return await database.fetchval("select id::text from facilities where code = $1", code)


async def seed() -> None:
    settings = get_settings()
    if not database.is_supabase_mode():
        print("SKIP: DATABASE_MODE is not supabase — nothing to seed.")
        return
    if not settings.allow_test_seed:
        print("SKIP: ALLOW_TEST_SEED is false — refusing to seed.")
        return

    marina = await _facility_id("FAC-DXB-MARINA")
    auh = await _facility_id("FAC-AUH-CENTRAL")
    if not marina:
        print("ERROR: facilities not found — run migrations 000016+ first.")
        return

    # --- facility owner login (scoped to Marina) ---------------------------
    owner = await users_repo.create(
        email=OWNER_EMAIL, password_hash=hash_password(OWNER_PASSWORD),
        full_name="Marina Facility Owner", role="facility_owner",
        facility_id=marina, created_by_seed=True,
    )
    print(f"facility_owner: {OWNER_EMAIL} / {OWNER_PASSWORD}  (facility_id={marina})")

    # --- settings (one row per facility) -----------------------------------
    for fid, cap in ((marina, 120), (auh, 80)):
        if not fid:
            continue
        await database.execute(
            """insert into facility_settings
                 (facility_id, accepting_orders, daily_capacity, quality_check_required,
                  preferred_handoff_window, is_test_data, created_by_seed, seed_source)
               values ($1, true, $2, true, '10:00-21:00', true, true, 'facility_dashboard_seed')
               on conflict (facility_id) do nothing""",
            fid, cap,
        )

    # --- weekly timings for Marina (Mon..Sat open, Sun closed) -------------
    for dow in range(7):
        closed = dow == 0  # Sunday closed (example)
        await database.execute(
            """insert into facility_timings
                 (facility_id, day_of_week, opens_at, closes_at, receiving_start, receiving_end,
                  handoff_start, handoff_end, same_day_cutoff, is_closed, is_test_data, created_by_seed, seed_source)
               values ($1,$2,$3::text::time,$4::text::time,$5::text::time,$6::text::time,
                       $7::text::time,$8::text::time,$9::text::time,$10,true,true,'facility_dashboard_seed')
               on conflict (facility_id, day_of_week) do nothing""",
            marina, dow,
            None if closed else _DEFAULT_HOURS["opens_at"],
            None if closed else _DEFAULT_HOURS["closes_at"],
            None if closed else _DEFAULT_HOURS["receiving_start"],
            None if closed else _DEFAULT_HOURS["receiving_end"],
            None if closed else _DEFAULT_HOURS["handoff_start"],
            None if closed else _DEFAULT_HOURS["handoff_end"],
            None if closed else _DEFAULT_HOURS["same_day_cutoff"],
            closed,
        )

    # --- notification contact (idempotent by facility+mobile) --------------
    contact_mobile = "+971500000111"
    exists = await database.fetchval(
        "select 1 from facility_notification_contacts where facility_id=$1 and mobile_e164=$2",
        marina, contact_mobile)
    if not exists:
        await database.execute(
            """insert into facility_notification_contacts
                 (facility_id, name, role, mobile_e164, mobile_masked, notification_types,
                  active, is_test_data, created_by_seed, seed_source)
               values ($1,'Operations Desk','facility_manager',$2,$3,
                       array['new_order_assigned','sla_risk','issue_response'],
                       true,true,true,'facility_dashboard_seed')""",
            marina, contact_mobile, mask_phone(contact_mobile))

    # --- team members ------------------------------------------------------
    if not await database.fetchval("select 1 from facility_team_members where facility_id=$1 limit 1", marina):
        for name, role, phone, vehicle in (
            ("Marina Facility Owner", "facility_owner", "+971500000111", None),
            ("Ravi (Runner)", "facility_driver", "+971500000222", "Motorbike"),
        ):
            await database.execute(
                """insert into facility_team_members
                     (facility_id, name, role, phone_e164, phone_masked, vehicle_type, status,
                      is_test_data, created_by_seed, seed_source)
                   values ($1,$2,$3,$4,$5,$6,'active',true,true,'facility_dashboard_seed')""",
                marina, name, role, phone, mask_phone(phone), vehicle)

    # --- one demo facility issue + thread ----------------------------------
    if not await database.fetchval("select 1 from facility_issues where facility_id=$1 limit 1", marina):
        issue = await database.fetchrow(
            """insert into facility_issues
                 (facility_id, issue_type, title, message, severity, priority, status,
                  created_by_label, is_test_data, created_by_seed, seed_source)
               values ($1,'instruction_unclear','Unclear stain instruction',
                       'Order has a note that is unclear about the stain treatment. Please confirm.',
                       'medium','normal','open','Marina Facility',
                       true,true,'facility_dashboard_seed')
               returning id""",
            marina)
        if issue:
            await database.execute(
                """insert into facility_issue_messages
                     (facility_issue_id, sender_type, sender_label, message, is_test_data, created_by_seed, seed_source)
                   values ($1,'facility','Marina Facility',
                           'Could you confirm whether the red stain on the shirt needs special handling?',
                           true,true,'facility_dashboard_seed')""",
                issue["id"])

    # --- one active driver assignment (→ one driver shows "On Job") ---------
    # Drivers themselves are seeded by migration 000023 (idempotent by phone).
    driver = await database.fetchrow(
        "select id from facility_drivers where facility_id=$1 and phone_e164=$2",
        marina, "+971500000333")  # Samir Ali (Van)
    if driver:
        has_active = await database.fetchval(
            "select 1 from driver_assignments where driver_id=$1 "
            "and status in ('assigned','in_progress') limit 1", driver["id"])
        order = await database.fetchrow(
            "select id, order_id, coalesce(service_display_name, service, 'Laundry') as svc, "
            "coalesce(pickup_area, area) as area from orders "
            "where facility_id=$1 and status in ('ready_for_delivery','in_cleaning','picked_up') "
            "order by created_at desc limit 1", marina)
        if order and not has_active:
            await database.execute(
                """insert into driver_assignments
                     (facility_id, driver_id, order_id, order_ref, task_type, service_summary,
                      status, expected_completion_at, area, is_test_data, created_by_seed, seed_source)
                   values ($1,$2,$3,$4,'facility_handoff',$5,'in_progress',
                           now() + interval '3 hours',$6,true,true,'facility_dashboard_seed')""",
                marina, driver["id"], order["id"], order["order_id"], order["svc"], order["area"])
            await database.execute(
                "update facility_drivers set status='handoff_in_progress' where id=$1", driver["id"])
            print(f"driver assignment: Samir Ali → {order['order_id']} (facility handoff)")

    print("Facility demo data seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
