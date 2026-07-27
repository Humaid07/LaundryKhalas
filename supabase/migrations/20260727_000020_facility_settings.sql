-- =====================================================================
-- LaundryKhalas — Facility settings: operations, timings, blackout,
-- team members, price-change requests
-- Migration: 20260727_000020_facility_settings
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Backs Settings → Operations / Timings / Teams / Price. Facilities can VIEW
-- agreed pricing and REQUEST a change (internal approval required — a facility
-- never changes platform-published customer prices directly). Team member
-- phones are stored full (backend-only) + masked for display.
-- Additive + idempotent.
-- =====================================================================

-- One operational-preferences row per facility.
create table if not exists facility_settings (
    id                    uuid primary key default gen_random_uuid(),
    facility_id           uuid not null unique references facilities(id) on delete cascade,
    accepting_orders      boolean not null default true,
    daily_capacity        integer,
    service_capacity_json jsonb not null default '{}',   -- {service_code: capacity}
    quality_check_required boolean not null default true,
    preferred_handoff_window text,
    operations_config_json jsonb not null default '{}',
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
alter table facility_settings enable row level security;
drop trigger if exists set_facility_settings_updated_at on facility_settings;
create trigger set_facility_settings_updated_at before update on facility_settings
    for each row execute function set_updated_at();


-- Weekly operating hours (one row per facility per day_of_week 0=Sun..6=Sat).
create table if not exists facility_timings (
    id               uuid primary key default gen_random_uuid(),
    facility_id      uuid not null references facilities(id) on delete cascade,
    day_of_week      smallint not null check (day_of_week between 0 and 6),
    opens_at         time,
    closes_at        time,
    receiving_start  time,
    receiving_end    time,
    handoff_start    time,
    handoff_end      time,
    same_day_cutoff  time,
    is_closed        boolean not null default false,
    is_test_data     boolean not null default false,
    is_demo          boolean not null default false,
    environment      text    not null default 'dev',
    seed_batch_id    text,
    seed_source      text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    unique (facility_id, day_of_week)
);
alter table facility_timings enable row level security;
drop trigger if exists set_facility_timings_updated_at on facility_timings;
create trigger set_facility_timings_updated_at before update on facility_timings
    for each row execute function set_updated_at();


create table if not exists facility_blackout_dates (
    id               uuid primary key default gen_random_uuid(),
    facility_id      uuid not null references facilities(id) on delete cascade,
    blackout_date    date not null,
    reason           text,
    is_test_data     boolean not null default false,
    is_demo          boolean not null default false,
    environment      text    not null default 'dev',
    seed_batch_id    text,
    seed_source      text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at       timestamptz not null default now(),
    unique (facility_id, blackout_date)
);
alter table facility_blackout_dates enable row level security;


create table if not exists facility_team_members (
    id               uuid primary key default gen_random_uuid(),
    facility_id      uuid not null references facilities(id) on delete cascade,
    name             text not null,
    role             text not null default 'facility_staff', -- facility_owner|facility_manager|facility_staff|facility_driver
    phone_e164       text,                                    -- backend-only full number
    phone_masked     text,                                    -- display
    vehicle_type     text,                                    -- driver/runner only
    responsibilities text,
    status           text not null default 'active' check (status in ('active', 'inactive')),
    last_activity_at timestamptz,
    is_test_data     boolean not null default false,
    is_demo          boolean not null default false,
    environment      text    not null default 'dev',
    seed_batch_id    text,
    seed_source      text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists facility_team_facility_idx on facility_team_members (facility_id, status);
alter table facility_team_members enable row level security;
drop trigger if exists set_facility_team_updated_at on facility_team_members;
create trigger set_facility_team_updated_at before update on facility_team_members
    for each row execute function set_updated_at();


-- Facility-initiated price-change requests → reviewed/approved by internal team.
-- Facilities never change published customer prices directly.
create table if not exists facility_price_change_requests (
    id               uuid primary key default gen_random_uuid(),
    facility_id      uuid not null references facilities(id) on delete cascade,
    item_code        text,                            -- catalogue service_items.item_code
    item_label       text,
    unit_type        text,
    current_price    numeric(12,2),
    requested_price  numeric(12,2),
    reason           text,
    status           text not null default 'pending'
                     check (status in ('pending', 'approved', 'rejected', 'cancelled')),
    decided_by       text,
    decision_note    text,
    requested_by_user_id uuid references public.users(id) on delete set null,
    is_test_data     boolean not null default false,
    is_demo          boolean not null default false,
    environment      text    not null default 'dev',
    seed_batch_id    text,
    seed_source      text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    decided_at       timestamptz
);
create index if not exists facility_price_requests_facility_idx on facility_price_change_requests (facility_id, status);
alter table facility_price_change_requests enable row level security;
drop trigger if exists set_facility_price_requests_updated_at on facility_price_change_requests;
create trigger set_facility_price_requests_updated_at before update on facility_price_change_requests
    for each row execute function set_updated_at();
