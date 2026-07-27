-- =====================================================================
-- LaundryKhalas — Facility notification contacts + notification log
-- Migration: 20260727_000019_facility_notifications
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Facilities register mobile numbers to be notified when a new order is
-- assigned (and for SLA risk, issue replies, payout updates, daily summary).
-- The notification SERVICE is mock-first + env-gated (services/facility_
-- notifications.py + FACILITY_NOTIFICATIONS_MODE): by default it only LOGS a
-- row here (status='mock_logged') and never sends externally. Notifications
-- never contain full customer address/phone.
-- Additive + idempotent.
-- =====================================================================

create table if not exists facility_notification_contacts (
    id                 uuid primary key default gen_random_uuid(),
    facility_id        uuid not null references facilities(id) on delete cascade,
    name               text not null,
    role               text,
    mobile_e164        text not null,                 -- backend-only full number
    mobile_masked      text,                          -- display (masked)
    notification_types text[] not null default '{}',  -- new_order_assigned|order_arrival_reminder|sla_risk|issue_response|payout_update|daily_summary
    active             boolean not null default true,
    -- standard test-data marker columns
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
create index if not exists facility_notif_contacts_facility_idx on facility_notification_contacts (facility_id, active);

alter table facility_notification_contacts enable row level security;

drop trigger if exists set_facility_notif_contacts_updated_at on facility_notification_contacts;
create trigger set_facility_notif_contacts_updated_at before update on facility_notification_contacts
    for each row execute function set_updated_at();


create table if not exists facility_notifications (
    id                  uuid primary key default gen_random_uuid(),
    facility_id         uuid not null references facilities(id) on delete cascade,
    order_id            uuid references orders(id) on delete set null,
    order_ref           text,
    type                text not null,                -- new_order_assigned|order_arrival_reminder|sla_risk|issue_response|payout_update|daily_summary
    channel             text not null default 'mock', -- mock|whatsapp|sms
    destination_masked  text,                         -- masked contact the message targeted
    status              text not null default 'mock_logged'
                        check (status in ('pending', 'sent', 'failed', 'mock_logged')),
    message_preview     text,
    provider            text,
    provider_message_id text,
    error               text,
    read_at             timestamptz,                  -- notification-center read state
    -- standard test-data marker columns
    is_test_data        boolean not null default false,
    is_demo             boolean not null default false,
    environment         text    not null default 'dev',
    seed_batch_id       text,
    seed_source         text,
    test_scenario_id    text,
    created_by_seed     boolean not null default false,
    created_at          timestamptz not null default now(),
    sent_at             timestamptz
);
create index if not exists facility_notifications_facility_idx on facility_notifications (facility_id, created_at desc);
create index if not exists facility_notifications_unread_idx on facility_notifications (facility_id, read_at);

alter table facility_notifications enable row level security;
