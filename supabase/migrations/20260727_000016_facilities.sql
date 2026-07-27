-- =====================================================================
-- LaundryKhalas — Facilities (laundry partners) + order→facility link
-- Migration: 20260727_000016_facilities
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Introduces the first-class `facilities` table (there was previously only a
-- free-text `orders.facility` column) and links orders to a facility via
-- `orders.facility_id`. Powers the new mobile-first Facility Dashboard
-- (apps/facility-dashboard) which is scoped per facility by the backend.
--
-- `payout_rate` is a nullable placeholder: facility payable/partner rates are
-- fed later. Until then Finance shows customer order value only ("Completed
-- Service Value") and payout is reported as pending — no payout is invented.
-- Additive + idempotent.
-- =====================================================================

create table if not exists facilities (
    id               uuid primary key default gen_random_uuid(),
    code             text unique not null,           -- stable business code
    name             text not null,
    area             text,                            -- area/city only (no full address)
    city             text,
    emirate          text,
    capacity_daily   integer,                         -- orders/day the facility can take
    operating_status text not null default 'open'
                     check (operating_status in ('open', 'closed', 'busy', 'paused')),
    is_active        boolean not null default true,
    payout_rate      numeric(6,4),                    -- PLACEHOLDER: facility payable rate, fed later (null = not set)
    contact_area     text,                            -- non-PII location label for ops
    notes            text,
    -- standard test-data marker columns
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
create index if not exists facilities_active_idx on facilities (is_active);

alter table facilities enable row level security;

drop trigger if exists set_facilities_updated_at on facilities;
create trigger set_facilities_updated_at before update on facilities
    for each row execute function set_updated_at();

-- Link orders to a facility (keep the legacy free-text `facility` for back-compat,
-- mirroring how service_id/service_display_name were added alongside `service`).
alter table orders add column if not exists facility_id uuid references facilities(id) on delete set null;
create index if not exists idx_orders_facility on orders (facility_id, status);

-- ---------------------------------------------------------------------
-- Seed: two demo facilities (idempotent on `code`). Always visible
-- (is_demo=false) so the facility dashboard has data in dev/test.
-- ---------------------------------------------------------------------
insert into facilities (code, name, area, city, emirate, capacity_daily, operating_status,
                        is_test_data, is_demo, environment, created_by_seed, seed_source)
values
    ('FAC-DXB-MARINA', 'Dubai Marina Facility', 'Dubai Marina', 'Dubai', 'Dubai', 120, 'open',
     true, false, 'dev', true, 'facility_dashboard_seed'),
    ('FAC-AUH-CENTRAL', 'Abu Dhabi Central Facility', 'Al Danah', 'Abu Dhabi', 'Abu Dhabi', 80, 'busy',
     true, false, 'dev', true, 'facility_dashboard_seed')
on conflict (code) do nothing;

-- Attach all existing non-draft orders that have no facility yet to the Marina
-- facility so the dashboard shows real order flow in dev/test.
update orders
   set facility_id = (select id from facilities where code = 'FAC-DXB-MARINA')
 where facility_id is null
   and status <> 'draft';
