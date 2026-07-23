-- =====================================================================
-- Laundry Khalas — ITEM-LEVEL SERVICE CATALOGUE + order pricing snapshot
-- Migration: 20260723_000007_service_catalogue
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Replaces the service-level-only pricing (one 'from' price per branded
-- service) with the real, normalized item catalogue from the approved Laundry
-- Khalas price-list image: 9 categories -> sub-category services -> priced
-- items (bold price = current_price; crossed-out = regular_price). The DB is the
-- runtime source of truth; scripts/seed_service_catalogue.py imports
-- apps/whatsapp-agent/config/laundry_catalogue.json into these tables
-- idempotently and records the source + verification date.
--
-- Also adds VAT-aware order pricing + a frozen line-item snapshot on `orders`
-- so a confirmed order's pricing never changes when the catalogue is updated
-- later (task spec §10). Prices EXCLUDE 5% VAT.
--
-- Everything is additive + idempotent (create ... if not exists / on conflict
-- do nothing), safe on top of 000001–000006 without touching existing rows.
-- =====================================================================

-- 1) Catalogue tables ---------------------------------------------------------
create table if not exists service_categories (
    id                 uuid primary key default gen_random_uuid(),
    code               text unique not null,          -- stable id, e.g. CLEAN_PRESS
    name               text not null,                 -- 'Clean & Press'
    description        text,
    sort_order         int  not null default 0,
    active             boolean not null default true,
    source             text,
    source_verified_at date,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create table if not exists services (
    id                 uuid primary key default gen_random_uuid(),
    category_id        uuid references service_categories(id) on delete cascade,
    code               text unique not null,          -- e.g. CLEAN_PRESS_EVERYDAY
    name               text not null,                 -- 'Everyday Wear'
    sort_order         int  not null default 0,
    active             boolean not null default true,
    source             text,
    source_verified_at date,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists services_category_idx on services(category_id);

create table if not exists service_items (
    id                 uuid primary key default gen_random_uuid(),
    service_id         uuid references services(id) on delete cascade,
    category_id        uuid references service_categories(id) on delete cascade,
    item_code          text unique not null,          -- e.g. CLEAN_PRESS_SHIRT
    canonical_name     text not null,                 -- 'Shirt'
    display_name       text,
    description        text,
    pricing_type       text not null default 'FIXED_PER_ITEM', -- FIXED_PER_ITEM|STARTING_FROM|PER_PAIR|PER_BAG|PER_KG|PER_SQM|INSPECTION_REQUIRED
    pricing_unit       text not null default 'ITEM',  -- ITEM|PAIR|BAG|KG|SQM
    current_price      numeric(12,2),                 -- bold price on the image (active selling price)
    regular_price      numeric(12,2),                 -- crossed-out earlier/regular price (NEVER the selling price)
    currency           text not null default 'AED',
    is_starting_price  boolean not null default false, -- 'From …'
    requires_inspection boolean not null default false,
    requires_measurement boolean not null default false,
    bag_limit_kg       numeric(6,2),                  -- Wash & Fold bag limit
    note               text,
    active             boolean not null default true,
    sort_order         int  not null default 0,
    source             text,
    source_verified_at date,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists service_items_category_idx on service_items(category_id);
create index if not exists service_items_service_idx  on service_items(service_id);
create index if not exists service_items_active_idx   on service_items(active);

-- Alias table (natural-language matching -> catalogue). An alias belongs to an
-- item (preferred) or a category (for step-1 selection).
create table if not exists service_aliases (
    id          uuid primary key default gen_random_uuid(),
    item_id     uuid references service_items(id) on delete cascade,
    category_id uuid references service_categories(id) on delete cascade,
    alias       text not null,
    created_at  timestamptz not null default now()
);
create unique index if not exists service_aliases_item_alias_key
    on service_aliases(item_id, alias) where item_id is not null;
create unique index if not exists service_aliases_category_alias_key
    on service_aliases(category_id, alias) where category_id is not null and item_id is null;

-- Lightweight price-version audit (task spec §3): the seed appends a row
-- whenever an item's current/regular price changes, so past prices are kept.
create table if not exists service_price_versions (
    id                 uuid primary key default gen_random_uuid(),
    item_code          text not null,
    current_price      numeric(12,2),
    regular_price      numeric(12,2),
    currency           text not null default 'AED',
    pricing_type       text,
    pricing_unit       text,
    source             text,
    source_verified_at date,
    recorded_at        timestamptz not null default now()
);
create index if not exists service_price_versions_item_idx on service_price_versions(item_code);

-- RLS on (dev/test posture matches the rest of the schema).
alter table service_categories     enable row level security;
alter table services               enable row level security;
alter table service_items          enable row level security;
alter table service_aliases        enable row level security;
alter table service_price_versions enable row level security;

drop trigger if exists set_service_categories_updated_at on service_categories;
create trigger set_service_categories_updated_at before update on service_categories
    for each row execute function set_updated_at();
drop trigger if exists set_services_updated_at on services;
create trigger set_services_updated_at before update on services
    for each row execute function set_updated_at();
drop trigger if exists set_service_items_updated_at on service_items;
create trigger set_service_items_updated_at before update on service_items
    for each row execute function set_updated_at();

-- 2) VAT-aware order pricing + frozen line-item snapshot on `orders` ----------
-- The priced line items chosen for the order, snapshotted at confirmation so a
-- later catalogue change never re-prices a historical order (task spec §10).
alter table orders add column if not exists line_items            jsonb;
alter table orders add column if not exists catalogue_category_code text;
alter table orders add column if not exists catalogue_category_name text;
alter table orders add column if not exists subtotal_amount       numeric(12,2);  -- excl. VAT, firm portion only
alter table orders add column if not exists vat_rate              numeric(5,4);   -- 0.0500
alter table orders add column if not exists vat_amount            numeric(12,2);
alter table orders add column if not exists estimated_total       numeric(12,2);  -- incl. VAT; mirrors `amount`
alter table orders add column if not exists pricing_is_estimated  boolean;        -- true when any 'from'/measured line
alter table orders add column if not exists pricing_snapshot_at   timestamptz;    -- when the snapshot was frozen
-- Transient item-collection cursors (the FSM's step-2/3 browsing state; cleared
-- once collection ends). Kept in the DB so the step survives a restart.
alter table orders add column if not exists browse_service_code   text;           -- sub-category whose items are shown
alter table orders add column if not exists pending_item_code     text;           -- item awaiting a quantity/measure
