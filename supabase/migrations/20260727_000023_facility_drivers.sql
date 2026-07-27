-- =====================================================================
-- LaundryKhalas — Facility drivers, driver assignments + status events
-- Migration: 20260727_000023_facility_drivers
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Drivers/runners linked to a facility, their live operational status, and
-- the order tasks (pickup / facility handoff / delivery / return) assigned to
-- them. This is the OPERATIONAL driver domain (the Facility Dashboard → Drivers
-- section). Settings → Teams remains the people-directory; a driver can be a
-- team member AND a facility_drivers row.
--
-- Also (same migration):
--   * facility_issues.driver_id     — link a driver issue to a driver.
--   * facility_notifications.issue_id + dedupe_key — issue-reply notifications +
--     DB-enforced idempotency (facility_id, dedupe_key).
--
-- Driver/notification records NEVER carry customer full phone/address/payment
-- (privacy firewall, CLAUDE.md §7). Additive + idempotent.
-- =====================================================================

-- --------------------------------------------------------------------
-- facility_drivers
-- --------------------------------------------------------------------
create table if not exists facility_drivers (
    id             uuid primary key default gen_random_uuid(),
    facility_id    uuid not null references facilities(id) on delete cascade,
    user_id        uuid references public.users(id) on delete set null,   -- future driver login
    name           text not null,
    phone_e164     text,                          -- backend-only full number
    phone_masked   text,                          -- display (masked)
    role           text not null default 'driver'
                   check (role in ('driver', 'runner', 'pickup_partner')),
    status         text not null default 'free'
                   check (status in ('free', 'assigned', 'pickup_in_progress', 'on_job',
                                     'at_facility', 'handoff_in_progress', 'delivery_in_progress',
                                     'completed_recently', 'on_break', 'offline', 'issue_reported')),
    vehicle_type   text,
    area           text,                          -- zone the driver covers
    active         boolean not null default true,
    last_active_at timestamptz,
    -- standard test-data marker columns
    is_test_data   boolean not null default false,
    is_demo        boolean not null default false,
    environment    text    not null default 'dev',
    seed_batch_id  text,
    seed_source    text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists facility_drivers_facility_idx on facility_drivers (facility_id, status);
create index if not exists facility_drivers_active_idx on facility_drivers (facility_id, active);

alter table facility_drivers enable row level security;

drop trigger if exists set_facility_drivers_updated_at on facility_drivers;
create trigger set_facility_drivers_updated_at before update on facility_drivers
    for each row execute function set_updated_at();


-- --------------------------------------------------------------------
-- driver_assignments  (an order task given to a driver)
-- --------------------------------------------------------------------
create table if not exists driver_assignments (
    id                    uuid primary key default gen_random_uuid(),
    facility_id           uuid not null references facilities(id) on delete cascade,
    driver_id             uuid not null references facility_drivers(id) on delete cascade,
    order_id              uuid references orders(id) on delete set null,
    order_ref             text,                    -- business order id snapshot
    task_type             text not null default 'facility_handoff'
                          check (task_type in ('pickup', 'facility_handoff', 'delivery', 'return')),
    service_summary       text,                    -- PII-safe service label only
    status                text not null default 'assigned'
                          check (status in ('assigned', 'in_progress', 'completed', 'cancelled', 'issue')),
    assigned_at           timestamptz not null default now(),
    started_at            timestamptz,
    completed_at          timestamptz,
    expected_completion_at timestamptz,
    area                  text,
    notes                 text,
    -- standard test-data marker columns
    is_test_data          boolean not null default false,
    is_demo               boolean not null default false,
    environment           text    not null default 'dev',
    seed_batch_id         text,
    seed_source           text,
    test_scenario_id      text,
    created_by_seed       boolean not null default false,
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);
create index if not exists driver_assignments_driver_idx on driver_assignments (driver_id, status);
create index if not exists driver_assignments_facility_idx on driver_assignments (facility_id, status);
create index if not exists driver_assignments_order_idx on driver_assignments (order_id);
-- At most one ACTIVE (assigned/in_progress) assignment per driver.
create unique index if not exists driver_assignments_active_driver_idx
    on driver_assignments (driver_id)
    where status in ('assigned', 'in_progress');

alter table driver_assignments enable row level security;

drop trigger if exists set_driver_assignments_updated_at on driver_assignments;
create trigger set_driver_assignments_updated_at before update on driver_assignments
    for each row execute function set_updated_at();


-- --------------------------------------------------------------------
-- driver_status_events  (audit trail of driver status changes)
-- --------------------------------------------------------------------
create table if not exists driver_status_events (
    id             uuid primary key default gen_random_uuid(),
    facility_id    uuid not null references facilities(id) on delete cascade,
    driver_id      uuid not null references facility_drivers(id) on delete cascade,
    status         text not null,
    order_id       uuid references orders(id) on delete set null,
    note           text,
    created_by     text,
    -- standard test-data marker columns
    is_test_data   boolean not null default false,
    is_demo        boolean not null default false,
    environment    text    not null default 'dev',
    seed_batch_id  text,
    seed_source    text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at     timestamptz not null default now()
);
create index if not exists driver_status_events_driver_idx on driver_status_events (driver_id, created_at desc);

alter table driver_status_events enable row level security;


-- --------------------------------------------------------------------
-- facility_issues.driver_id — link driver issues to a driver
-- --------------------------------------------------------------------
alter table facility_issues
    add column if not exists driver_id uuid references facility_drivers(id) on delete set null;
create index if not exists facility_issues_driver_idx on facility_issues (driver_id);


-- --------------------------------------------------------------------
-- facility_notifications.issue_id + dedupe_key
--   * issue_id  — issue-reply notifications point at a facility_issue.
--   * dedupe_key — DB-enforced idempotency so an order status change / driver
--     assignment / issue reply is never notified twice.
-- --------------------------------------------------------------------
alter table facility_notifications
    add column if not exists issue_id uuid references facility_issues(id) on delete set null;
alter table facility_notifications
    add column if not exists dedupe_key text;
create unique index if not exists facility_notifications_dedupe_idx
    on facility_notifications (facility_id, dedupe_key)
    where dedupe_key is not null;


-- --------------------------------------------------------------------
-- Seed: 3 demo drivers for the Marina facility (idempotent by phone).
-- One assignment (→ on_job) is seeded by scripts/seed_facility_data.py so the
-- Drivers page shows a "free vs on job" split out of the box.
-- --------------------------------------------------------------------
insert into facility_drivers
    (facility_id, name, phone_e164, phone_masked, role, status, vehicle_type, area,
     active, is_test_data, created_by_seed, seed_source, environment)
select f.id, v.name, v.phone, v.masked, v.role, v.status, v.vehicle, v.area,
       true, true, true, 'facility_drivers_migration', 'dev'
from facilities f
cross join (values
    ('Ravi Kumar',   '+971500000222', '+971•••••0222', 'runner', 'free',     'Motorbike', 'Dubai Marina'),
    ('Samir Ali',    '+971500000333', '+971•••••0333', 'driver', 'free',     'Van',       'JBR / Marina'),
    ('Deepa Nair',   '+971500000444', '+971•••••0444', 'runner', 'on_break', 'Motorbike', 'Dubai Marina')
) as v(name, phone, masked, role, status, vehicle, area)
where f.code = 'FAC-DXB-MARINA'
  and not exists (
      select 1 from facility_drivers d
      where d.facility_id = f.id and d.phone_e164 = v.phone
  );
