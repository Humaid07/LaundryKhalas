-- =====================================================================
-- LaundryKhalas — Facility service-availability + rates + margin rules (mock)
-- Migration: 20260728_000027_facility_rates_margin
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Backs the location-based BETTER-RATE workflow: pick the lowest-cost qualified
-- nearby facility that OFFERS the service, apply the active MARGIN rule, and return
-- only the customer-facing price — facility cost + margin are NEVER exposed
-- (CLAUDE.md §7). Adds geo/market/accepts_orders to facilities, plus:
--   * facility_services — which services each facility performs (+ bespoke_ok)
--   * facility_rates    — facility internal cost per service (mock)
--   * margin_rules      — margin applied on top of the facility rate
-- All rates here are MOCK. Additive + idempotent.
-- =====================================================================

alter table facilities add column if not exists market            text;
alter table facilities add column if not exists country           text;
alter table facilities add column if not exists latitude          numeric(9,6);
alter table facilities add column if not exists longitude         numeric(9,6);
alter table facilities add column if not exists accepts_orders    boolean not null default true;
alter table facilities add column if not exists service_radius_km numeric(6,2);

create table if not exists facility_services (
    id            uuid primary key default gen_random_uuid(),
    facility_id   uuid not null references facilities (id) on delete cascade,
    service_code  text not null,                 -- catalogue category code (e.g. CLEAN_PRESS)
    offered       boolean not null default true,
    bespoke_ok    boolean not null default false,
    created_at    timestamptz not null default now(),
    unique (facility_id, service_code)
);
create index if not exists idx_facility_services_code on facility_services (service_code);

create table if not exists facility_rates (
    id            uuid primary key default gen_random_uuid(),
    facility_id   uuid not null references facilities (id) on delete cascade,
    service_code  text not null,
    rate          numeric(12,2) not null,         -- MOCK internal cost per unit/order
    currency      text not null default 'AED',
    active        boolean not null default true,
    valid_from    date,
    valid_to      date,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (facility_id, service_code)
);
create index if not exists idx_facility_rates_code on facility_rates (service_code);

create table if not exists margin_rules (
    id            uuid primary key default gen_random_uuid(),
    code          text unique not null,
    scope         text not null default 'default',  -- default|service|bespoke
    service_code  text,                              -- null for default/bespoke
    margin_type   text not null default 'percentage',-- percentage|fixed
    margin_value  numeric(12,2) not null,
    active        boolean not null default true,
    priority      integer not null default 0,        -- higher wins
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

alter table facility_services enable row level security;
alter table facility_rates    enable row level security;
alter table margin_rules      enable row level security;

drop trigger if exists set_facility_rates_updated_at on facility_rates;
create trigger set_facility_rates_updated_at before update on facility_rates
    for each row execute function set_updated_at();
drop trigger if exists set_margin_rules_updated_at on margin_rules;
create trigger set_margin_rules_updated_at before update on margin_rules
    for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- MOCK seed: geo + market for the two seeded facilities, service coverage,
-- internal rates, and a default 40% margin rule. Idempotent.
-- ---------------------------------------------------------------------
update facilities set market = 'AE', country = 'AE',
       latitude = 25.0805, longitude = 55.1403, accepts_orders = true, service_radius_km = 25
 where code = 'FAC-DXB-MARINA';
update facilities set market = 'AE', country = 'AE',
       latitude = 24.4539, longitude = 54.3773, accepts_orders = true, service_radius_km = 30
 where code = 'FAC-AUH-CENTRAL';

insert into facility_services (facility_id, service_code, offered, bespoke_ok)
select f.id, s.code, true, s.bespoke
from facilities f
cross join (values
    ('WASH_FOLD', false), ('CLEAN_PRESS', false), ('PRESS_ONLY', false),
    ('SHOE_CARE', true), ('BAG_CARE', true)
) as s(code, bespoke)
where f.code in ('FAC-DXB-MARINA', 'FAC-AUH-CENTRAL')
on conflict (facility_id, service_code) do nothing;

insert into facility_rates (facility_id, service_code, rate)
select f.id, r.code, r.rate
from facilities f
join (values
    ('FAC-DXB-MARINA','WASH_FOLD', 30.00), ('FAC-DXB-MARINA','CLEAN_PRESS', 6.00),
    ('FAC-DXB-MARINA','PRESS_ONLY', 4.00), ('FAC-DXB-MARINA','SHOE_CARE', 32.00),
    ('FAC-DXB-MARINA','BAG_CARE', 45.00),
    ('FAC-AUH-CENTRAL','WASH_FOLD', 28.00), ('FAC-AUH-CENTRAL','CLEAN_PRESS', 7.00),
    ('FAC-AUH-CENTRAL','PRESS_ONLY', 3.50), ('FAC-AUH-CENTRAL','SHOE_CARE', 30.00),
    ('FAC-AUH-CENTRAL','BAG_CARE', 48.00)
) as r(fcode, code, rate) on r.fcode = f.code
on conflict (facility_id, service_code) do nothing;

insert into margin_rules (code, scope, margin_type, margin_value, active, priority)
values ('DEFAULT-40', 'default', 'percentage', 40.00, true, 0),
       ('BESPOKE-55', 'bespoke', 'percentage', 55.00, true, 10)
on conflict (code) do nothing;
