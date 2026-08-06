-- =====================================================================
-- LaundryKhalas — Facility quotation lifecycle + customer memory + feedback
-- Migration: 20260806_000050_quotation_memory_feedback
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- EXTENDS existing scaffolds (no parallel quotation system):
--   * facility_quote_revisions (mig 000048) gains the provisional/versioned quote
--     lifecycle + pricing snapshot fields.
--   * NEW immutable customer_quote_snapshots + customer_quote_approvals.
--   * NEW durable customer_memory (+ history) with scope/confidence/PATCH provenance.
--   * NEW customer_feedback_events + feedback_review_actions + global_rule_change_candidates.
--   * NEW order_context_links (media + message → order/item isolation).
--
-- All additive + idempotent. New tables RLS-deny anon/authenticated. No production
-- data mutated.
--
-- Rollback: drop the new tables + the added facility_quote_revisions columns.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. facility_quote_revisions — provisional + versioned quote lifecycle
-- ---------------------------------------------------------------------
alter table facility_quote_revisions add column if not exists quote_version integer not null default 1;
alter table facility_quote_revisions add column if not exists request_status text;   -- DRAFT..CANCELLED (spec §6)
alter table facility_quote_revisions add column if not exists pricing_state text;     -- provisional_pricing states
alter table facility_quote_revisions add column if not exists provisional_minimum numeric(12,2);
alter table facility_quote_revisions add column if not exists provisional_maximum numeric(12,2);
alter table facility_quote_revisions add column if not exists photo_status text;       -- provided | not_provided | requested
alter table facility_quote_revisions add column if not exists inspection_status text;  -- pending | required | done
alter table facility_quote_revisions add column if not exists service_code text;
alter table facility_quote_revisions add column if not exists work_requirement text;
alter table facility_quote_revisions add column if not exists requires_operations_review boolean not null default false;
alter table facility_quote_revisions add column if not exists markup_rule_id text;
alter table facility_quote_revisions add column if not exists expires_at timestamptz;
alter table facility_quote_revisions add column if not exists source_message_id text;

-- One active quote per (order, item, version); new scope/price = a NEW version.
create unique index if not exists uq_quote_order_item_version
  on facility_quote_revisions (order_id, order_item_id, quote_version);

-- ---------------------------------------------------------------------
-- 2. customer_quote_snapshots — immutable markup calculation
-- ---------------------------------------------------------------------
create table if not exists customer_quote_snapshots (
  id                  uuid primary key default gen_random_uuid(),
  quote_revision_id   uuid references facility_quote_revisions (id) on delete cascade,
  order_id            uuid references orders (id) on delete cascade,
  order_item_id       text,
  quote_version       integer not null default 1,
  facility_fee        numeric(12,2),
  markup_type         text,
  markup_value        numeric(12,4),
  markup_rule_id      text,
  customer_subtotal   numeric(12,2),
  discount_percentage numeric(6,2),
  discount_amount     numeric(12,2),
  delivery_charge     numeric(12,2),
  express_surcharge   numeric(12,2),
  final_customer_price numeric(12,2),
  currency            text not null default 'AED',
  pricing_rule_version text,
  is_test_data        boolean not null default false,
  created_at          timestamptz not null default now()
);
create index if not exists idx_customer_quote_snapshots_order on customer_quote_snapshots (order_id, order_item_id);

-- ---------------------------------------------------------------------
-- 3. customer_quote_approvals — the customer's decision on a version
-- ---------------------------------------------------------------------
create table if not exists customer_quote_approvals (
  id                  uuid primary key default gen_random_uuid(),
  order_id            uuid references orders (id) on delete cascade,
  order_item_id       text,
  quote_revision_id   uuid references facility_quote_revisions (id) on delete set null,
  quote_version       integer not null default 1,
  decision            text not null check (decision in ('APPROVED','DECLINED','NEEDS_CLARIFICATION','NO_RESPONSE')),
  final_price         numeric(12,2),
  scope               text,
  customer_message_id text,
  decided_at          timestamptz not null default now(),
  is_test_data        boolean not null default false
);
create unique index if not exists uq_quote_approval_version
  on customer_quote_approvals (order_id, order_item_id, quote_version, decision);
create index if not exists idx_quote_approvals_order on customer_quote_approvals (order_id, order_item_id);

-- ---------------------------------------------------------------------
-- 4. customer_memory (+ history) — durable, scoped, PATCH-provenance
-- ---------------------------------------------------------------------
create table if not exists customer_memory (
  id                uuid primary key default gen_random_uuid(),
  customer_id       uuid references customers (id) on delete cascade,
  memory_type       text not null,     -- NAME | ADDRESS | CONTACT_PREFERENCE | PAYMENT_PREFERENCE | SERVICE_PREFERENCE | ...
  memory_key        text not null,
  memory_value      text,
  source_message_id text,
  source_order_id   uuid,
  scope             text not null default 'CUSTOMER_GLOBAL'
                    check (scope in ('CUSTOMER_GLOBAL','ADDRESS_SPECIFIC','SERVICE_SPECIFIC','ORDER_ONLY')),
  confidence        numeric(4,3),
  customer_confirmed boolean not null default false,
  status            text not null default 'active'
                    check (status in ('active','superseded','invalidated')),
  valid_from        timestamptz not null default now(),
  invalidated_at    timestamptz,
  is_test_data      boolean not null default false,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
-- One ACTIVE value per (customer, key, scope).
create unique index if not exists uq_customer_memory_active
  on customer_memory (customer_id, memory_key, scope) where status = 'active';
create index if not exists idx_customer_memory_customer on customer_memory (customer_id, status);

create table if not exists customer_memory_history (
  id           uuid primary key default gen_random_uuid(),
  customer_id  uuid,
  memory_id    uuid,
  memory_key   text,
  old_value    text,
  new_value    text,
  reason       text,
  superseded_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 5. customer_feedback_events + review actions + rule-change candidates
-- ---------------------------------------------------------------------
create table if not exists customer_feedback_events (
  id                  uuid primary key default gen_random_uuid(),
  customer_id         uuid references customers (id) on delete set null,
  conversation_id     uuid,
  order_id            uuid,
  order_item_id       text,
  feedback_type       text not null,    -- CUSTOMER_CORRECTION | NAME_CORRECTION | ADDRESS_CORRECTION | ...
  scope               text not null default 'unknown' check (scope in ('customer','global','unknown')),
  affected_service    text,
  affected_reply      text,
  raw_text            text,
  provider            text,
  provider_message_id text,
  status              text not null default 'new'
                      check (status in ('new','reviewed','approved','rejected','duplicate')),
  is_test_data        boolean not null default false,
  created_at          timestamptz not null default now()
);
-- Idempotency: one feedback of a type per provider message.
create unique index if not exists uq_feedback_provider_msg_type
  on customer_feedback_events (provider, provider_message_id, feedback_type)
  where provider is not null and provider_message_id is not null;
create index if not exists idx_feedback_status on customer_feedback_events (status, created_at desc);

create table if not exists feedback_review_actions (
  id                uuid primary key default gen_random_uuid(),
  feedback_event_id uuid references customer_feedback_events (id) on delete cascade,
  action            text not null,     -- approve_customer_memory | approve_global_candidate | reject | duplicate | ...
  actor             text,
  notes             text,
  created_at        timestamptz not null default now()
);

create table if not exists global_rule_change_candidates (
  id                uuid primary key default gen_random_uuid(),
  feedback_event_id uuid references customer_feedback_events (id) on delete set null,
  target            text not null,     -- system_prompt | service_rule | price_rule | classifier | template | global_memory
  proposed_change   text,
  status            text not null default 'proposed'
                    check (status in ('proposed','approved','rejected','deployed')),
  approved_by       text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 6. order_context_links — media + message → order/item isolation
-- ---------------------------------------------------------------------
create table if not exists order_context_links (
  id                  uuid primary key default gen_random_uuid(),
  customer_id         uuid,
  conversation_id     uuid,
  order_id            uuid references orders (id) on delete cascade,
  order_item_id       text,
  provider_message_id text,
  media_id            uuid,
  link_type           text not null,   -- media | message | quote | payment | issue
  media_purpose       text,
  upload_source       text,
  created_at          timestamptz not null default now()
);
create index if not exists idx_order_context_links_order on order_context_links (order_id);
create index if not exists idx_order_context_links_msg on order_context_links (provider_message_id) where provider_message_id is not null;

-- ---------------------------------------------------------------------
-- RLS — deny anon/authenticated on every new table (service role bypasses).
-- ---------------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array[
    'customer_quote_snapshots','customer_quote_approvals','customer_memory',
    'customer_memory_history','customer_feedback_events','feedback_review_actions',
    'global_rule_change_candidates','order_context_links'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('revoke all on %I from anon, authenticated', t);
    execute format('drop policy if exists %I_no_public_access on %I', t, t);
    execute format('create policy %I_no_public_access on %I as restrictive for all to anon, authenticated using (false) with check (false)', t, t);
  end loop;
end $$;
