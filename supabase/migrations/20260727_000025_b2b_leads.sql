-- =====================================================================
-- LaundryKhalas — B2B leads (hotel / commercial / bulk / partnership)
-- Migration: 20260727_000025_b2b_leads
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- B2B enquiries (hotel laundry, restaurant linen, uniform cleaning, bulk
-- outsourcing, facility partnerships, business pricing) must NOT be forced
-- through the consumer pickup funnel and must NOT be counted in consumer
-- conversion metrics. They get their own lead entity routed to the commercial
-- team. Detection already exists (escalation category b2b_quotation); this adds
-- the durable record. Additive + idempotent.
-- =====================================================================

create table if not exists b2b_leads (
    id                  uuid primary key default gen_random_uuid(),
    lead_ref            text unique not null,            -- e.g. B2B-XXXXXXXX
    customer_id         uuid references customers (id) on delete set null,
    conversation_id     uuid references conversations (id) on delete set null,
    company_name        text,
    contact_person      text,
    business_type       text not null default 'other',   -- hotel|restaurant|uniform|commercial_laundry|bulk_outsourcing|facility_partnership|other
    location            text,                             -- area/city label only (no full private address required)
    market              text,                             -- AE|QA|... for combined + country reporting
    estimated_volume    text,
    required_services   text,
    frequency           text,
    current_provider    text,
    preferred_meeting_time text,
    notes               text,
    assigned_team       text not null default 'Sales / Partner Acquisition',
    status              text not null default 'new',      -- new|contacted|qualifying|proposal|won|lost
    source              text not null default 'whatsapp',
    -- standard test-data markers
    is_test_data       boolean not null default false,
    is_demo            boolean not null default false,
    environment        text    not null default 'dev',
    seed_batch_id      text,
    seed_source        text,
    test_scenario_id   text,
    created_by_seed    boolean not null default false,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists idx_b2b_leads_status on b2b_leads (status);
create index if not exists idx_b2b_leads_market on b2b_leads (market);

alter table b2b_leads enable row level security;

drop trigger if exists set_b2b_leads_updated_at on b2b_leads;
create trigger set_b2b_leads_updated_at before update on b2b_leads
    for each row execute function set_updated_at();
