-- =====================================================================
-- LaundryKhalas — Facility-raised issues + threaded messages
-- Migration: 20260727_000018_facility_issues
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Facilities raise operational issues (delay, missing/damaged item, unclear
-- instruction, capacity full, closure, payout/pricing, etc.) to the internal
-- LaundryKhalas team. Each issue has a threaded conversation between the
-- facility and internal ops. Mirrors the `tickets` + `messages` pattern.
-- Privacy: issues store area/city + order business-id only, never customer PII.
-- Additive + idempotent.
-- =====================================================================

create table if not exists facility_issues (
    id               uuid primary key default gen_random_uuid(),
    facility_id      uuid not null references facilities(id) on delete cascade,
    order_id         uuid references orders(id) on delete set null,
    order_ref        text,                            -- business order id snapshot (e.g. LK-2026-000004)
    conversation_id  uuid references conversations(id) on delete set null,
    issue_type       text not null,                   -- order_delay|item_missing|item_damaged|wrong_details|driver_no_show|instruction_unclear|capacity_full|facility_closed|payment_issue|pricing_issue|other
    title            text,
    message          text not null,                   -- opening message
    severity         text not null default 'medium'   -- Critical|High|Medium (display) — stored lower
                     check (severity in ('critical', 'high', 'medium')),
    priority         text not null default 'normal'   -- normal|high|urgent
                     check (priority in ('normal', 'high', 'urgent')),
    assigned_team    text not null default 'Facility Facing',
    assigned_internal_owner text,
    status           text not null default 'open'
                     check (status in ('open', 'acknowledged', 'waiting_on_facility',
                                       'waiting_on_internal_team', 'resolved', 'closed')),
    requested_help   text,
    created_by_user_id uuid references public.users(id) on delete set null,
    created_by_label text,                            -- non-PII display label of the raiser
    -- standard test-data marker columns
    is_test_data     boolean not null default false,
    is_demo          boolean not null default false,
    environment      text    not null default 'dev',
    seed_batch_id    text,
    seed_source      text,
    test_scenario_id text,
    created_by_seed  boolean not null default false,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    resolved_at      timestamptz
);
create index if not exists facility_issues_facility_idx on facility_issues (facility_id, status);
create index if not exists facility_issues_status_idx on facility_issues (status);

alter table facility_issues enable row level security;

drop trigger if exists set_facility_issues_updated_at on facility_issues;
create trigger set_facility_issues_updated_at before update on facility_issues
    for each row execute function set_updated_at();


create table if not exists facility_issue_messages (
    id                uuid primary key default gen_random_uuid(),
    facility_issue_id uuid not null references facility_issues(id) on delete cascade,
    sender_type       text not null check (sender_type in ('facility', 'internal', 'system')),
    sender_id         uuid references public.users(id) on delete set null,
    sender_label      text,                           -- non-PII display label
    message           text not null,
    attachment_urls   jsonb not null default '[]',
    is_internal       boolean not null default false, -- internal-only note (never shown to facility)
    -- standard test-data marker columns
    is_test_data      boolean not null default false,
    is_demo           boolean not null default false,
    environment       text    not null default 'dev',
    seed_batch_id     text,
    seed_source       text,
    test_scenario_id  text,
    created_by_seed   boolean not null default false,
    created_at        timestamptz not null default now()
);
create index if not exists facility_issue_messages_issue_idx on facility_issue_messages (facility_issue_id, created_at);

alter table facility_issue_messages enable row level security;
