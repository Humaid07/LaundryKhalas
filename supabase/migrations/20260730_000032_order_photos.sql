-- =====================================================================
-- LaundryKhalas — Facility order photos (intake + pre-dispatch proof)
-- Migration: 20260730_000032_order_photos
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds ONE table, `order_photos`, so a laundry partner/facility can attach
-- garment photos to an order at two operational stages — when items are
-- RECEIVED at the facility (intake) and BEFORE handoff/dispatch (pre_dispatch).
-- Photos are proof / QC / dispute-and-damage evidence for internal ops.
--
-- Design notes:
--   * The FILE lives in object/local storage; only METADATA lives here. The
--     column `storage_key` locates the bytes; base64 image data is NEVER stored
--     in the DB (spec + CLAUDE.md §16 "smallest safe working version").
--   * Every row carries both `order_id` (orders UUID FK) AND `facility_id` so
--     every read/write is scoped to the caller's facility — the isolation
--     boundary the app enforces (facilities' service role bypasses RLS).
--   * `stage` is constrained to the two IMPLEMENTED stages plus three reserved
--     FUTURE stages (damage_report/issue_photo/quality_check) so adding them
--     later needs no schema change; the API only accepts intake/pre_dispatch.
--   * Standard test-data marker columns match orders/order_events so seeded
--     development rows are clearly flagged and swept by the reset scripts.
--   * RLS deny posture mirrors facility_audit_log (000030): revoke from the
--     PostgREST roles + a restrictive deny policy; the backend service role
--     bypasses RLS and is the only reader/writer.
--
-- Additive + idempotent (safe to run more than once).
--
-- Rollback:
--   drop policy if exists order_photos_no_public_access on order_photos;
--   drop table if exists order_photos;
-- =====================================================================

create table if not exists order_photos (
    id                  uuid primary key default gen_random_uuid(),
    order_id            uuid not null references orders (id) on delete cascade,
    facility_id         uuid references facilities (id) on delete set null,
    -- intake | pre_dispatch  (+ reserved: damage_report | issue_photo | quality_check)
    stage               text not null,
    -- local | supabase | r2  (dev/local default; cloud providers added later)
    storage_provider    text not null default 'local',
    storage_key         text not null,            -- locates the bytes in storage
    public_url          text,                     -- set only for a public provider
    file_name           text not null,            -- safe generated name (no PII)
    content_type        text not null,            -- image/jpeg | image/png | image/webp
    file_size           bigint not null default 0,
    uploaded_by_user_id uuid,                     -- users.id (nullable; dev principal has none)
    uploaded_by_name    text,
    metadata            jsonb not null default '{}'::jsonb,
    -- test-data markers (match orders / order_events)
    is_test_data        boolean not null default false,
    is_demo             boolean not null default false,
    environment         text    not null default 'dev',
    seed_batch_id       text,
    seed_source         text,
    created_by_seed     boolean not null default false,
    created_at          timestamptz not null default now(),
    deleted_at          timestamptz               -- soft-delete (never hard-delete evidence)
);

-- stage vocabulary (implemented + reserved future stages).
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'order_photos_stage_chk') then
        alter table order_photos add constraint order_photos_stage_chk
            check (stage in ('intake', 'pre_dispatch', 'damage_report', 'issue_photo', 'quality_check'));
    end if;
end $$;

-- storage provider vocabulary.
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'order_photos_provider_chk') then
        alter table order_photos add constraint order_photos_provider_chk
            check (storage_provider in ('local', 'supabase', 'r2'));
    end if;
end $$;

-- Live reads are "photos for this order+stage, not deleted" and "counts per
-- order for the list badges" — both scoped by facility.
create index if not exists idx_order_photos_order
    on order_photos (order_id, stage) where deleted_at is null;
create index if not exists idx_order_photos_facility
    on order_photos (facility_id) where deleted_at is null;

-- RLS: deny the public PostgREST roles; the backend service role bypasses RLS.
alter table order_photos enable row level security;
revoke all on order_photos from anon, authenticated;
drop policy if exists order_photos_no_public_access on order_photos;
create policy order_photos_no_public_access on order_photos
    as restrictive for all to anon, authenticated
    using (false) with check (false);
