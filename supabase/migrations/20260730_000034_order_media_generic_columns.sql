-- =====================================================================
-- LaundryKhalas — order_photos → unified order-media record (R2-ready)
-- Migration: 20260730_000034_order_media_generic_columns
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Context / naming decision (see docs/architecture/media-storage-r2.md):
--   Rather than create a second, parallel `order_media` table, we EXTEND the
--   existing `order_photos` table (000032) into the unified, R2-backed
--   order-level media record. The table name stays `order_photos` (stable for
--   the existing facility routes/UI); it now carries generic media columns and
--   an expanded stage vocabulary so future media types need no schema churn.
--
--   Column-name mapping (existing → generic concept):
--     storage_key  == object_key         (locates the bytes; PII-safe key)
--     file_size    == file_size_bytes
--     file_name    == generated safe name (client's ORIGINAL filename is
--                     deliberately NOT stored — it can carry customer PII;
--                     CLAUDE.md §7 privacy firewall)
--     stage        == media_stage
--   These are intentionally NOT duplicated with new columns.
--
--   Files still live in object storage (local dev folder or Cloudflare R2);
--   only METADATA lives here. base64 media is NEVER stored in the DB.
--
-- Additive + idempotent (safe to run more than once).
--
-- Rollback:
--   alter table order_photos
--     drop column if exists bucket,
--     drop column if exists checksum_sha256,
--     drop column if exists width,
--     drop column if exists height,
--     drop column if exists duration_seconds,
--     drop column if exists source_channel,
--     drop column if exists visibility_scope,
--     drop column if exists status;
--   (the expanded stage CHECK can be reverted to the 000032 list)
-- =====================================================================

-- New generic media columns (all nullable / safe-defaulted → no backfill needed).
alter table order_photos
    add column if not exists bucket           text,               -- object-store bucket (R2); null for local
    add column if not exists checksum_sha256  text,               -- content hash (integrity / de-dupe / audit)
    add column if not exists width            integer,            -- image width  (optional; null until extracted)
    add column if not exists height           integer,            -- image height (optional; null until extracted)
    add column if not exists duration_seconds numeric,            -- for future video/audio media
    add column if not exists source_channel   text not null default 'facility_dashboard',
    add column if not exists visibility_scope text not null default 'facility',   -- facility | internal | customer
    add column if not exists status           text not null default 'active';     -- active | quarantined | deleted

-- Expand the stage vocabulary: the two IMPLEMENTED facility stages plus reserved
-- future stages (customer_reference / damage_report / issue_photo / quality_check
-- / pickup_proof / delivery_proof). The facility API still only accepts
-- intake/pre_dispatch; the rest need no further schema change to enable later.
alter table order_photos drop constraint if exists order_photos_stage_chk;
alter table order_photos add constraint order_photos_stage_chk
    check (stage in (
        'intake', 'pre_dispatch',
        'customer_reference', 'damage_report', 'issue_photo',
        'quality_check', 'pickup_proof', 'delivery_proof'
    ));

-- Constrain the new enum-like columns.
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'order_photos_visibility_chk') then
        alter table order_photos add constraint order_photos_visibility_chk
            check (visibility_scope in ('facility', 'internal', 'customer'));
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'order_photos_status_chk') then
        alter table order_photos add constraint order_photos_status_chk
            check (status in ('active', 'quarantined', 'deleted'));
    end if;
end $$;

-- Helpful when internal ops later filters media by visibility.
create index if not exists idx_order_photos_visibility
    on order_photos (order_id, visibility_scope) where deleted_at is null;
