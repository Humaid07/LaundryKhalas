-- =====================================================================
-- LaundryKhalas — CRM funnel stage + customer segments (deterministic)
-- Migration: 20260727_000022_crm_segments
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds a DETERMINISTIC CRM layer on the existing `customers` table: a single
-- lifecycle_stage, a single funnel_stage, and a set of descriptive segments,
-- plus the aggregates they are derived from. These are computed by backend
-- rules only (services/crm_segments.py + db/repositories/crm_repo.py) — never
-- assigned by the LLM (CLAUDE.md: deterministic backend stays authoritative).
--
-- All columns are additive + idempotent; a cache of a pure recomputation, so
-- they can always be rebuilt from orders/flags. Nothing here is customer-facing.
-- =====================================================================

alter table customers add column if not exists lifecycle_stage      text;
alter table customers add column if not exists funnel_stage         text;
-- Descriptive segment tags (e.g. ["repeat_customer","high_value"]). jsonb array.
alter table customers add column if not exists segments             jsonb not null default '[]'::jsonb;
-- Aggregates the segments are derived from (a recomputation cache).
alter table customers add column if not exists confirmed_order_count integer     not null default 0;
alter table customers add column if not exists lifetime_value        numeric(12,2) not null default 0;
alter table customers add column if not exists discount_request_count integer    not null default 0;
alter table customers add column if not exists price_enquiry_count    integer    not null default 0;  -- fed by a later funnel slice
alter table customers add column if not exists has_open_complaint     boolean    not null default false;
alter table customers add column if not exists is_b2b                 boolean    not null default false;
alter table customers add column if not exists last_order_at          timestamptz;
alter table customers add column if not exists last_activity_at       timestamptz;
alter table customers add column if not exists segments_computed_at   timestamptz;

create index if not exists idx_customers_lifecycle_stage on customers (lifecycle_stage);
create index if not exists idx_customers_funnel_stage    on customers (funnel_stage);

comment on column customers.lifecycle_stage is
  'Single primary CRM lifecycle (lead|active_customer|repeat_customer|inactive|complaint_open|b2b_lead). Deterministic, recomputed by crm_repo.';
comment on column customers.segments is
  'jsonb array of descriptive segment tags. Deterministic, non-exclusive. Never set by the LLM.';
