-- =====================================================================
-- LaundryKhalas — Campaigns + attribution (mock-first)
-- Migration: 20260728_000026_campaigns
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Outbound promo/campaign context must be tracked SEPARATELY from normal customer
-- intent (spec). `campaigns` holds definitions (offer, market, validity, attribution
-- window); `campaign_sends` records each recipient + their response/booking so we can
-- do last-touch attribution and mark campaign responders — WITHOUT treating a campaign
-- reply as ordinary intent. The backend validates eligibility/expiry; the agent never
-- grants an expired/ineligible offer. Additive + idempotent.
-- =====================================================================

create table if not exists campaigns (
    id                    uuid primary key default gen_random_uuid(),
    code                  text unique not null,
    name                  text not null,
    campaign_type         text not null default 'promo',   -- promo|acquisition|retention|review|winback
    offer                 text,
    discount_percentage   numeric(5,2),
    market                text,                              -- AE|QA|... (null = all)
    valid_from            date,
    valid_to              date,
    attribution_window_days integer not null default 30,
    active                boolean not null default true,
    -- markers
    is_test_data       boolean not null default false,
    is_demo            boolean not null default false,
    environment        text    not null default 'dev',
    created_by_seed    boolean not null default false,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create table if not exists campaign_sends (
    id                    uuid primary key default gen_random_uuid(),
    campaign_id           uuid references campaigns (id) on delete cascade,
    customer_id           uuid references customers (id) on delete set null,
    conversation_id       uuid references conversations (id) on delete set null,
    sent_at               timestamptz not null default now(),
    response_at           timestamptz,
    booking_confirmed_at  timestamptz,
    order_id              uuid references orders (id) on delete set null,
    revenue               numeric(12,2),
    discount_amount       numeric(12,2),
    attribution           text not null default 'last_touch',
    status                text not null default 'sent',      -- sent|responded|converted
    -- markers
    is_test_data       boolean not null default false,
    is_demo            boolean not null default false,
    environment        text    not null default 'dev',
    created_by_seed    boolean not null default false,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists idx_campaign_sends_customer on campaign_sends (customer_id);
create index if not exists idx_campaign_sends_campaign on campaign_sends (campaign_id);

alter table campaigns      enable row level security;
alter table campaign_sends enable row level security;

drop trigger if exists set_campaigns_updated_at on campaigns;
create trigger set_campaigns_updated_at before update on campaigns
    for each row execute function set_updated_at();
drop trigger if exists set_campaign_sends_updated_at on campaign_sends;
create trigger set_campaign_sends_updated_at before update on campaign_sends
    for each row execute function set_updated_at();
