-- =====================================================================
-- Laundry Khalas — DELIVERY SLA / turnaround + Express + delivery estimate
-- Migration: 20260723_000010_delivery_sla
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- DB-driven delivery SLA (task spec §§23-25): a `delivery_sla_rules` catalogue
-- (seeded from config/delivery_sla.json) + a frozen delivery estimate snapshot
-- on `orders` so a confirmed order's promised turnaround never changes when the
-- SLA rules change later. Express = 12h for eligible services only; the Express
-- surcharge stays NULL until the business configures it (never invented).
--
-- Additive + idempotent, safe on top of 000001–000009.
-- =====================================================================

-- 1) SLA rule catalogue -------------------------------------------------------
create table if not exists delivery_sla_rules (
    id                 uuid primary key default gen_random_uuid(),
    code               text unique not null,          -- e.g. SLA_SHOE_CARE
    match_category_code text,                          -- category default rule
    match_item_codes   text[],                         -- item-level override
    min_hours          int  not null,
    max_hours          int  not null,
    day_type           text not null default 'CALENDAR', -- CALENDAR | WORKING
    express_eligible   boolean not null default false,
    priority           int  not null default 0,        -- higher wins (item > category)
    display_text       text not null,                  -- '2–3 days'
    active             boolean not null default true,
    source             text,
    source_verified_at date,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists delivery_sla_rules_active_idx on delivery_sla_rules(active);

alter table delivery_sla_rules enable row level security;
drop trigger if exists set_delivery_sla_rules_updated_at on delivery_sla_rules;
create trigger set_delivery_sla_rules_updated_at before update on delivery_sla_rules
    for each row execute function set_updated_at();

-- 2) Frozen delivery estimate snapshot on `orders` ----------------------------
alter table orders add column if not exists delivery_mode              text;        -- STANDARD | EXPRESS
alter table orders add column if not exists turnaround_rule_codes      text[];
alter table orders add column if not exists turnaround_min_hours       int;
alter table orders add column if not exists turnaround_max_hours       int;
alter table orders add column if not exists turnaround_day_type        text;
alter table orders add column if not exists turnaround_text            text;
alter table orders add column if not exists estimated_delivery_start_at timestamptz;
alter table orders add column if not exists estimated_delivery_end_at   timestamptz;
alter table orders add column if not exists estimated_delivery_text     text;
alter table orders add column if not exists express_eligible            boolean;
alter table orders add column if not exists express_applied             boolean;
