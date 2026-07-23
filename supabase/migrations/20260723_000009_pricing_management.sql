-- =====================================================================
-- Laundry Khalas — PRICING MANAGEMENT: versioning, promotions, audit, sync
-- Migration: 20260723_000009_pricing_management
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Builds on 000007 (item catalogue in service_categories/services/service_items).
-- Adds a versioned publishing model so admins edit a DRAFT without touching live
-- customer-facing pricing, then PUBLISH atomically; runtime consumers (WhatsApp
-- agent, public website API, dashboard) read exactly ONE current published
-- version. Promotions live in their own time-bounded table and overlay the
-- published base at runtime (so a promo can start/end with no deploy). Every
-- material change is written to an immutable audit log. Historical order pricing
-- is already frozen on `orders` (000007) and is never touched here.
--
-- Additive + idempotent. Prices EXCLUDE 5% VAT unless prices_include_vat=true.
-- =====================================================================

-- 1) Catalogue versions — the unit of publishing/rollback -------------------
create table if not exists catalogue_versions (
    id                   uuid primary key default gen_random_uuid(),
    version_number       int  not null,
    status               text not null default 'draft'
                         check (status in ('draft','pending_review','published','archived')),
    is_current           boolean not null default false,   -- exactly one published+current
    market               text not null default 'AE',
    change_summary       text,
    source               text,                              -- 'admin_edit' | 'import' | 'rollback' | 'seed'
    rollback_of_version  int,                               -- version_number this rolls back to
    created_by           text,
    published_by         text,
    created_at           timestamptz not null default now(),
    published_at         timestamptz,
    effective_at         timestamptz,                       -- when a scheduled publish becomes live
    updated_at           timestamptz not null default now()
);
create unique index if not exists catalogue_versions_number_market_key
    on catalogue_versions(version_number, market);
-- At most one current published version per market.
create unique index if not exists catalogue_versions_one_current
    on catalogue_versions(market) where is_current;

-- 2) Version items — the immutable price snapshot for a version -------------
create table if not exists catalogue_version_items (
    id                   uuid primary key default gen_random_uuid(),
    version_id           uuid not null references catalogue_versions(id) on delete cascade,
    item_code            text not null,
    category_code        text,
    category_name        text,
    service_code         text,
    service_name         text,
    canonical_name       text not null,
    display_name         text,
    description          text,
    pricing_type         text not null default 'FIXED_PER_ITEM',
    pricing_unit         text not null default 'ITEM',
    current_price        numeric(12,2),
    regular_price        numeric(12,2),
    currency             text not null default 'AED',
    is_starting_price    boolean not null default false,
    requires_inspection  boolean not null default false,
    requires_measurement boolean not null default false,
    vat_rate             numeric(5,4) not null default 0.0500,
    prices_include_vat   boolean not null default false,
    market               text not null default 'AE',
    active               boolean not null default true,
    sort_order           int not null default 0,
    disclaimer           text,          -- customer-facing
    internal_note        text,          -- NEVER exposed publicly
    created_at           timestamptz not null default now()
);
create unique index if not exists catalogue_version_items_key
    on catalogue_version_items(version_id, item_code);
create index if not exists catalogue_version_items_version_idx
    on catalogue_version_items(version_id);

-- 3) Promotions — time-bounded overlay on the published base ----------------
create table if not exists pricing_promotions (
    id            uuid primary key default gen_random_uuid(),
    item_code     text not null,
    name          text not null,
    description   text,
    promo_price   numeric(12,2) not null,
    currency      text not null default 'AED',
    market        text not null default 'AE',
    priority      int  not null default 0,     -- higher wins on overlap
    starts_at     timestamptz,
    ends_at       timestamptz,
    active        boolean not null default true,
    created_by    text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
create index if not exists pricing_promotions_item_idx on pricing_promotions(item_code);
create index if not exists pricing_promotions_window_idx on pricing_promotions(active, starts_at, ends_at);

-- 4) Immutable audit log — every material pricing change --------------------
create table if not exists pricing_audit_log (
    id            uuid primary key default gen_random_uuid(),
    action        text not null,           -- create|edit|activate|deactivate|publish|rollback|promo_start|promo_end|import
    entity_type   text not null,           -- item|version|promotion
    entity_ref    text,                    -- item_code | version_number | promo id
    field         text,
    old_value     text,
    new_value     text,
    actor         text,
    version_id    uuid references catalogue_versions(id) on delete set null,
    reason        text,
    created_at    timestamptz not null default now()
);
create index if not exists pricing_audit_log_entity_idx on pricing_audit_log(entity_type, entity_ref);
create index if not exists pricing_audit_log_created_idx on pricing_audit_log(created_at);

-- 5) Sync status — record website/cache sync attempts (§14/§19) -------------
create table if not exists pricing_sync_status (
    id            uuid primary key default gen_random_uuid(),
    target        text not null,           -- 'website' | 'whatsapp_cache'
    version_id    uuid references catalogue_versions(id) on delete set null,
    version_number int,
    status        text not null,           -- 'success' | 'failed' | 'pending'
    detail        text,
    attempted_at  timestamptz not null default now()
);
create index if not exists pricing_sync_status_target_idx on pricing_sync_status(target, attempted_at);

-- 6) RLS on (dev/test posture matches the rest of the schema) ---------------
alter table catalogue_versions      enable row level security;
alter table catalogue_version_items enable row level security;
alter table pricing_promotions      enable row level security;
alter table pricing_audit_log       enable row level security;
alter table pricing_sync_status     enable row level security;

drop trigger if exists set_catalogue_versions_updated_at on catalogue_versions;
create trigger set_catalogue_versions_updated_at before update on catalogue_versions
    for each row execute function set_updated_at();
drop trigger if exists set_pricing_promotions_updated_at on pricing_promotions;
create trigger set_pricing_promotions_updated_at before update on pricing_promotions
    for each row execute function set_updated_at();
