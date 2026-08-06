-- =====================================================================
-- LaundryKhalas — Advanced routing engine + trial-facility test environment
-- Migration: 20260806_000049_advanced_routing
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- One shared routing engine evaluates the same eligibility/availability/ranking
-- for TEST and PRODUCTION orders. This migration adds the facility routing
-- attributes, driver availability fields, specialist capabilities, and the
-- routing-decision snapshot store that the engine reads/writes.
--
-- All additive + idempotent. New tables RLS-deny anon/authenticated (service role
-- bypasses), matching the rest of the schema. No production data is mutated.
--
-- Rollback: drop the added columns + the new tables (see end of file).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. facilities — routing attributes + test-facility flag
-- ---------------------------------------------------------------------
alter table facilities add column if not exists is_test_facility boolean not null default false;
alter table facilities add column if not exists rating numeric(3,2);                 -- 0..5 aggregate
alter table facilities add column if not exists review_count integer not null default 0;
alter table facilities add column if not exists recent_order_success_rate numeric(5,2);
alter table facilities add column if not exists pickup_success_rate numeric(5,2);
alter table facilities add column if not exists delivery_success_rate numeric(5,2);
alter table facilities add column if not exists complaint_rate numeric(5,2);
alter table facilities add column if not exists performance_updated_at timestamptz;
-- Test/override workload %; production workload is computed live from order load.
alter table facilities add column if not exists current_workload_pct numeric(5,2);
alter table facilities add column if not exists max_concurrent_orders integer;
alter table facilities add column if not exists supports_express boolean not null default false;
alter table facilities add column if not exists turnaround_hours integer;
alter table facilities add column if not exists capacity_level text;                 -- LOW|MEDIUM|HIGH (informational)

create index if not exists idx_facilities_test on facilities (is_test_facility) where is_test_facility;

-- ---------------------------------------------------------------------
-- 2. facility_services — per-service express support
-- ---------------------------------------------------------------------
alter table facility_services add column if not exists express_ok boolean not null default false;

-- ---------------------------------------------------------------------
-- 3. facility_capabilities — specialist capabilities (leather, wedding, etc.)
-- ---------------------------------------------------------------------
create table if not exists facility_capabilities (
  id               uuid primary key default gen_random_uuid(),
  facility_id      uuid not null references facilities (id) on delete cascade,
  capability_code  text not null,           -- e.g. LEATHER, WEDDING_DRESSES, CARPET_MEASUREMENT
  is_test_data     boolean not null default false,
  is_demo          boolean not null default false,
  environment      text    not null default 'dev',
  seed_source      text,
  created_by_seed  boolean not null default false,
  created_at       timestamptz not null default now()
);
create unique index if not exists uq_facility_capability on facility_capabilities (facility_id, capability_code);
create index if not exists idx_facility_capabilities_fac on facility_capabilities (facility_id);

alter table facility_capabilities enable row level security;
revoke all on facility_capabilities from anon, authenticated;
drop policy if exists facility_capabilities_no_public_access on facility_capabilities;
create policy facility_capabilities_no_public_access on facility_capabilities
  as restrictive for all to anon, authenticated using (false) with check (false);

-- ---------------------------------------------------------------------
-- 4. facility_drivers — availability model + test-driver flag
-- ---------------------------------------------------------------------
alter table facility_drivers add column if not exists is_test_driver boolean not null default false;
alter table facility_drivers add column if not exists driver_code text;
alter table facility_drivers add column if not exists employment_status text not null default 'active';  -- active|inactive|on_leave
alter table facility_drivers add column if not exists shift_start time;
alter table facility_drivers add column if not exists shift_end time;
alter table facility_drivers add column if not exists break_start time;
alter table facility_drivers add column if not exists break_end time;
alter table facility_drivers add column if not exists service_days integer[];         -- 0=Sun..6=Sat; null = all days
alter table facility_drivers add column if not exists express_eligible boolean not null default false;
alter table facility_drivers add column if not exists max_concurrent_assignments integer not null default 1;
alter table facility_drivers add column if not exists leave_start timestamptz;
alter table facility_drivers add column if not exists leave_end timestamptz;
alter table facility_drivers add column if not exists available_from timestamptz;
alter table facility_drivers add column if not exists available_until timestamptz;
alter table facility_drivers add column if not exists latitude numeric(9,6);
alter table facility_drivers add column if not exists longitude numeric(9,6);
alter table facility_drivers add column if not exists last_location_update timestamptz;

create unique index if not exists uq_facility_driver_code on facility_drivers (driver_code) where driver_code is not null;
create index if not exists idx_facility_drivers_test on facility_drivers (is_test_driver) where is_test_driver;

-- ---------------------------------------------------------------------
-- 5. routing_decisions — the decision snapshot (test + production)
-- ---------------------------------------------------------------------
create table if not exists routing_decisions (
  id                          uuid primary key default gen_random_uuid(),
  order_id                    uuid references orders (id) on delete set null,
  order_ref                   text,
  environment                 text not null default 'dev',       -- TEST | production
  routing_mode                text not null,                     -- off|shadow|canary|live|simulator
  routing_version             text not null default 'ADVANCED_ROUTING_V1',
  simulation_time             timestamptz,
  customer_area               text,
  customer_latitude           numeric(9,6),
  customer_longitude          numeric(9,6),
  requested_service           text,
  service_subtype             text,
  required_capabilities       text[],
  requested_priority          text,                              -- standard | express
  requested_pickup_at         timestamptz,
  required_turnaround_hours   integer,
  candidates                  jsonb not null default '[]'::jsonb, -- full per-candidate breakdown
  eligible_count              integer not null default 0,
  rejected_count              integer not null default 0,
  score_components            jsonb,
  selected_facility_id        uuid,
  selected_driver_id          uuid,
  selected_pickup_slot_id     text,
  selection_reason            text,
  -- shadow-mode comparison
  legacy_selected_facility_id uuid,
  advanced_selected_facility_id uuid,
  selections_matched          boolean,
  fallback_used               boolean not null default false,
  created_by                  text,
  -- test-data markers
  is_test_data                boolean not null default false,
  is_demo                     boolean not null default false,
  seed_source                 text,
  created_by_seed             boolean not null default false,
  created_at                  timestamptz not null default now()
);
create index if not exists idx_routing_decisions_order on routing_decisions (order_id);
create index if not exists idx_routing_decisions_env_created on routing_decisions (environment, created_at desc);
create index if not exists idx_routing_decisions_mismatch on routing_decisions (selections_matched) where selections_matched = false;

alter table routing_decisions enable row level security;
revoke all on routing_decisions from anon, authenticated;
drop policy if exists routing_decisions_no_public_access on routing_decisions;
create policy routing_decisions_no_public_access on routing_decisions
  as restrictive for all to anon, authenticated using (false) with check (false);

-- ---------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------
-- drop table if exists routing_decisions;
-- drop table if exists facility_capabilities;
-- alter table facility_services drop column if exists express_ok;
-- alter table facilities drop column if exists is_test_facility, drop column if exists rating,
--   drop column if exists review_count, drop column if exists recent_order_success_rate,
--   drop column if exists pickup_success_rate, drop column if exists delivery_success_rate,
--   drop column if exists complaint_rate, drop column if exists performance_updated_at,
--   drop column if exists current_workload_pct, drop column if exists max_concurrent_orders,
--   drop column if exists supports_express, drop column if exists turnaround_hours,
--   drop column if exists capacity_level;
-- alter table facility_drivers drop column if exists is_test_driver, drop column if exists driver_code,
--   drop column if exists employment_status, drop column if exists shift_start, ... (see columns above)
