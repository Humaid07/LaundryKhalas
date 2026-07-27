-- =====================================================================
-- LaundryKhalas — Structured complaints + durable pending operational tasks
-- Migration: 20260727_000024_complaints_pending_tasks
-- (renumbered from 000023 to avoid a collision with a concurrent session's
--  20260727_000023_facility_drivers.sql — the tables are disjoint.)
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Two new operational tables:
--   * complaints      — a structured complaint record (category / item / photo ref /
--                       requested resolution / urgency), replacing the previous
--                       generic ticket-only handling. The agent NEVER promises a
--                       refund/compensation (CLAUDE.md §6); a complaint is raised for
--                       Operations to resolve.
--   * pending_tasks   — durable "I'll get back to you" tasks so a conversational
--                       promise ("let me check with the facility") becomes a tracked
--                       item with a due time, follow-up and escalation. Covers the 7
--                       AWAITING_* task types.
-- Additive + idempotent.
-- =====================================================================

create table if not exists complaints (
    id                  uuid primary key default gen_random_uuid(),
    complaint_ref       text unique not null,           -- e.g. CMP-3F9A21C4
    customer_id         uuid references customers (id) on delete set null,
    conversation_id     uuid references conversations (id) on delete set null,
    order_id            uuid references orders (id) on delete set null,
    order_ref           text,                            -- business order id as given by the customer
    category            text not null,                   -- delay_collection|delay_delivery|poor_cleaning|poor_pressing|shrinking|damage|missing_items|damp|incorrect_alteration|refund_request|reprocessing|facility_disagreement|other
    affected_item       text,
    description         text,
    photo_ref           text,                            -- media reference/caption only (no media bytes stored; bespoke media deferred)
    requested_resolution text,                           -- refund|reclean|reprocess|replacement|apology|other|unknown
    needs_recollection  boolean not null default false,
    urgency             text not null default 'medium',  -- low|medium|high|urgent
    status              text not null default 'open',    -- open|in_review|resolved|closed
    source              text not null default 'whatsapp',
    resolution_notes    text,
    -- standard test-data markers
    is_test_data       boolean not null default false,
    is_demo            boolean not null default false,
    environment        text    not null default 'dev',
    seed_batch_id      text,
    seed_source        text,
    test_scenario_id   text,
    created_by_seed    boolean not null default false,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    resolved_at        timestamptz
);
create index if not exists idx_complaints_status   on complaints (status);
create index if not exists idx_complaints_customer on complaints (customer_id);

create table if not exists pending_tasks (
    id                          uuid primary key default gen_random_uuid(),
    task_ref                    text unique,
    customer_id                 uuid references customers (id) on delete set null,
    conversation_id             uuid references conversations (id) on delete set null,
    order_id                    uuid references orders (id) on delete set null,
    complaint_id                uuid references complaints (id) on delete set null,
    quote_id                    text,
    task_type                   text not null,   -- AWAITING_FACILITY_QUOTE|AWAITING_FACILITY_APPROVAL|AWAITING_DRIVER_CONFIRMATION|AWAITING_OPERATIONS_RESPONSE|AWAITING_CUSTOMER_PHOTO|AWAITING_CUSTOMER_LOCATION|AWAITING_PAYMENT|AWAITING_COMPLAINT_REVIEW
    responsible_team            text,
    responsible_facility_id     uuid references facilities (id) on delete set null,
    status                      text not null default 'open',   -- open|in_progress|done|cancelled|escalated
    due_at                      timestamptz,
    follow_up_at                timestamptz,
    escalation_rule             text,
    escalated                   boolean not null default false,
    customer_notification_status text not null default 'none',  -- none|notified|pending
    notes                       text,
    metadata                    jsonb not null default '{}'::jsonb,
    -- standard test-data markers
    is_test_data       boolean not null default false,
    is_demo            boolean not null default false,
    environment        text    not null default 'dev',
    seed_batch_id      text,
    seed_source        text,
    test_scenario_id   text,
    created_by_seed    boolean not null default false,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    resolved_at        timestamptz
);
create index if not exists idx_pending_tasks_status  on pending_tasks (status);
create index if not exists idx_pending_tasks_type    on pending_tasks (task_type);
create index if not exists idx_pending_tasks_due     on pending_tasks (due_at);

alter table complaints     enable row level security;
alter table pending_tasks  enable row level security;

drop trigger if exists set_complaints_updated_at on complaints;
create trigger set_complaints_updated_at before update on complaints
    for each row execute function set_updated_at();
drop trigger if exists set_pending_tasks_updated_at on pending_tasks;
create trigger set_pending_tasks_updated_at before update on pending_tasks
    for each row execute function set_updated_at();
