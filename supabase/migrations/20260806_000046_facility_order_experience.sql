-- =====================================================================
-- LaundryKhalas — Facility order experience (cards + detail redesign)
-- Migration: 20260806_000046_facility_order_experience
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Backs the redesigned Facility Dashboard order cards + detail view:
--   * order_notes.priority — NORMAL | IMPORTANT | CRITICAL so genuinely
--     critical operational instructions (existing damage, do-not-process,
--     luxury handling) can stand out. Default NORMAL; the serializer also
--     derives a priority from category/keywords when it is left NORMAL.
--   * order_photos: per-item linkage + facility-facing metadata
--       - order_item_id  (which line item a photo belongs to; null = general)
--       - caption        (human caption shown under the thumbnail)
--       - source         (CUSTOMER | DRIVER | OPERATIONS | FACILITY_BEFORE_PROCESSING
--                         | FACILITY_AFTER_PROCESSING | FACILITY_ISSUE | INSPECTION)
--   * orders: immutable per-order facility-fee snapshot (never recomputed from a
--     newer rate card) — facility_fee_snapshot (jsonb) + facility_fee_total +
--     facility_fee_currency.
--   * facility_order_reviews — the "I have reviewed the order details, notes and
--     photos" acknowledgement, versioned so a later critical note / photo /
--     amendment invalidates it and forces a re-acknowledgement before the
--     facility may start processing.
--
-- Design notes:
--   * All additive `add column if not exists` / `create table if not exists`.
--   * priority + source + stage values are CHECK-constrained to approved vocab.
--   * RLS: deny anon/authenticated (service role — the backend — bypasses),
--     matching orders/order_notes/order_photos posture.
--   * Versions are integer signals COMPUTED from live data (note-row count,
--     live-photo count, amendment count) — see services/facility_order_view.py.
--     No trigger maintains them; they are stamped onto the review at ack time
--     and recompared on read.
--
-- Additive + idempotent (safe to run more than once).
--
-- Rollback:
--   drop policy if exists facility_order_reviews_no_public_access on facility_order_reviews;
--   drop table if exists facility_order_reviews;
--   alter table order_notes  drop column if exists priority;
--   alter table order_photos drop column if exists order_item_id;
--   alter table order_photos drop column if exists caption;
--   alter table order_photos drop column if exists source;
--   alter table orders drop column if exists facility_fee_snapshot;
--   alter table orders drop column if exists facility_fee_total;
--   alter table orders drop column if exists facility_fee_currency;
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. order_notes — priority level
-- ---------------------------------------------------------------------
alter table order_notes add column if not exists priority text not null default 'NORMAL';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'order_notes_priority_check') then
    alter table order_notes add constraint order_notes_priority_check
      check (priority in ('NORMAL','IMPORTANT','CRITICAL'));
  end if;
end $$;

-- ---------------------------------------------------------------------
-- 2. order_photos — per-item linkage + facility-facing metadata
-- ---------------------------------------------------------------------
-- order_item_id is a soft reference to a line item (items are JSON on the order,
-- so there is no FK target); null means the photo is a general order photo.
alter table order_photos add column if not exists order_item_id text;
alter table order_photos add column if not exists caption text;
-- Photo provenance shown to the facility (distinct from `stage`, which is the
-- processing checkpoint). Nullable for legacy rows; the serializer infers a
-- sensible source from stage when this is null.
alter table order_photos add column if not exists source text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'order_photos_source_check') then
    alter table order_photos add constraint order_photos_source_check
      check (source is null or source in (
        'CUSTOMER','DRIVER','OPERATIONS','FACILITY_BEFORE_PROCESSING',
        'FACILITY_AFTER_PROCESSING','FACILITY_ISSUE','INSPECTION'
      ));
  end if;
end $$;

create index if not exists idx_order_photos_order_item on order_photos (order_item_id) where order_item_id is not null;

-- ---------------------------------------------------------------------
-- 3. orders — immutable facility-fee snapshot
-- ---------------------------------------------------------------------
-- Frozen at facility handoff; a later rate-card change must NOT retro-price an
-- existing order. facility_fee_snapshot is the full FacilityCostResult.to_snapshot()
-- dict (per-item + totals); facility_fee_total/_currency are the denormalised
-- headline values for cards/finance. Margin/Stripe/customer price never live here.
alter table orders add column if not exists facility_fee_snapshot jsonb;
alter table orders add column if not exists facility_fee_total numeric(12,2);
alter table orders add column if not exists facility_fee_currency text;

-- ---------------------------------------------------------------------
-- 4. facility_order_reviews — versioned "details reviewed" acknowledgement
-- ---------------------------------------------------------------------
create table if not exists facility_order_reviews (
  id                  uuid primary key default gen_random_uuid(),
  order_id            uuid not null references orders (id) on delete cascade,
  facility_id         uuid not null,
  facility_user_id    text,                       -- null in dev (no login)
  order_version       integer not null default 0,
  notes_version       integer not null default 0,
  photo_version       integer not null default 0,
  acknowledged_at     timestamptz not null default now(),
  invalidated_at      timestamptz,
  invalidation_reason text,
  -- test-data markers (repo convention)
  is_test_data        boolean not null default false,
  is_demo             boolean not null default false,
  environment         text    not null default 'dev',
  seed_source         text,
  created_by_seed     boolean not null default false,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists idx_facility_order_reviews_order on facility_order_reviews (order_id);
create index if not exists idx_facility_order_reviews_scope on facility_order_reviews (facility_id, order_id);
-- Latest live acknowledgement per (order, facility) is read by acknowledged_at desc.

alter table facility_order_reviews enable row level security;
revoke all on facility_order_reviews from anon, authenticated;
drop policy if exists facility_order_reviews_no_public_access on facility_order_reviews;
create policy facility_order_reviews_no_public_access on facility_order_reviews
  as restrictive for all to anon, authenticated using (false) with check (false);
