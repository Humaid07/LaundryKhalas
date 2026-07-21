-- =====================================================================
-- LaundryKhalas — WhatsApp Agent DEV/TEST schema (initial)
-- Migration: 20260721_000001_initial_whatsapp_agent_dev_schema
--
-- Target: the SEPARATE dev/test Supabase project ONLY. This is NOT
-- production. A production Supabase project will be created later with its
-- own auth/RLS design. Do not run production assumptions against this.
--
-- Conventions
--   * UUID primary keys via gen_random_uuid() (core in PG13+).
--   * timestamptz everywhere; created_at/updated_at where useful.
--   * jsonb for metadata/payload columns.
--   * Every business table carries the standard test-data marker columns
--     (see test_data_cols note below) so seeded rows are always
--     identifiable and safely resettable.
--   * RLS is ENABLED on every table with NO anon/authenticated policies:
--     the PostgREST (frontend) surface is therefore denied by default.
--     The backend connects over a direct Postgres connection using the
--     service role (DATABASE_URL / service_role key) which bypasses RLS.
--     Dashboard → FastAPI → Supabase; the dashboard never talks to
--     Supabase directly. Production RLS/auth is designed later.
--
-- Standard test-data marker columns present on every business table:
--   is_test_data     boolean not null default false
--   is_demo          boolean not null default false
--   environment      text    not null default 'dev'
--   seed_batch_id    text
--   seed_source      text
--   test_scenario_id text
--   created_by_seed  boolean not null default false
-- =====================================================================

create extension if not exists pgcrypto;

-- Shared trigger to maintain updated_at on UPDATE.
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------
-- customers
-- ---------------------------------------------------------------------
create table if not exists customers (
  id                 uuid primary key default gen_random_uuid(),
  display_name       text,
  phone_e164         text,
  phone_hash         text,
  masked_phone       text,
  preferred_language text default 'en',
  city               text,
  area               text,
  region             text,
  market             text,
  source_channel     text default 'whatsapp',
  -- test-data markers
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
create index if not exists idx_customers_phone_hash on customers (phone_hash);
create index if not exists idx_customers_seed_batch on customers (seed_batch_id);
create index if not exists idx_customers_environment on customers (environment);

-- ---------------------------------------------------------------------
-- conversations
-- ---------------------------------------------------------------------
create table if not exists conversations (
  id                          uuid primary key default gen_random_uuid(),
  customer_id                 uuid references customers (id) on delete set null,
  external_conversation_id    text,
  channel                     text not null default 'whatsapp',
  status                      text not null default 'bot',      -- bot | human_needed | human_takeover | resolved
  priority                    text,                              -- urgent | high | medium | low | null
  human_intervention_required boolean not null default false,
  handoff_reason              text,
  assigned_team               text,
  linked_order_id             text,                              -- business order id (e.g. LK-AE-1024)
  last_message                text,
  last_message_at             timestamptz,
  unread_count                integer not null default 0,
  -- test-data markers
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
create index if not exists idx_conversations_customer on conversations (customer_id);
create index if not exists idx_conversations_status on conversations (status);
create index if not exists idx_conversations_priority on conversations (priority);
create index if not exists idx_conversations_hir on conversations (human_intervention_required);
create index if not exists idx_conversations_last_msg_at on conversations (last_message_at desc);
create index if not exists idx_conversations_seed_batch on conversations (seed_batch_id);

-- ---------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------
create table if not exists messages (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references conversations (id) on delete cascade,
  sender_type      text not null,           -- customer | agent | human | system
  message_text     text not null,
  is_internal      boolean not null default false,
  status           text default 'sent',
  metadata         jsonb default '{}'::jsonb,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now()
);
create index if not exists idx_messages_conversation on messages (conversation_id, created_at);
create index if not exists idx_messages_sender_type on messages (sender_type);
create index if not exists idx_messages_seed_batch on messages (seed_batch_id);

-- ---------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------
create table if not exists orders (
  id               uuid primary key default gen_random_uuid(),
  order_id         text unique not null,     -- business id, e.g. LK-AE-1024
  conversation_id  uuid references conversations (id) on delete set null,
  customer_id      uuid references customers (id) on delete set null,
  customer_name    text,
  service          text,
  items            jsonb default '[]'::jsonb,
  region           text,
  market           text,
  country          text,
  city             text,
  area             text,
  pickup_slot      text,
  delivery_slot    text,
  facility         text,
  driver           text,
  status           text not null default 'active',
  payment_status   text,
  payment_method   text,
  amount           numeric(12,2),
  source_channel   text default 'whatsapp',
  notes            text,
  change_request   text,
  completed_at     timestamptz,
  -- test-data markers
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
create index if not exists idx_orders_order_id on orders (order_id);
create index if not exists idx_orders_status on orders (status);
create index if not exists idx_orders_conversation on orders (conversation_id);
create index if not exists idx_orders_seed_batch on orders (seed_batch_id);

-- ---------------------------------------------------------------------
-- order_events (status/audit trail)
-- ---------------------------------------------------------------------
create table if not exists order_events (
  id               uuid primary key default gen_random_uuid(),
  order_id         uuid not null references orders (id) on delete cascade,
  event_type       text not null,
  from_status      text,
  to_status        text,
  actor_type       text,        -- customer | agent | human | system
  actor_name       text,
  notes            text,
  metadata         jsonb default '{}'::jsonb,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now()
);
create index if not exists idx_order_events_order on order_events (order_id, created_at);
create index if not exists idx_order_events_seed_batch on order_events (seed_batch_id);

-- ---------------------------------------------------------------------
-- agent_flags (handoff / escalation)
-- ---------------------------------------------------------------------
create table if not exists agent_flags (
  id                          uuid primary key default gen_random_uuid(),
  conversation_id             uuid references conversations (id) on delete cascade,
  order_id                    uuid references orders (id) on delete set null,
  flag_type                   text not null,   -- refund_request | damaged_item | missing_item | payment_issue | b2b_lead | complaint | ...
  priority                    text,            -- urgent | high | medium | low
  assigned_team               text,
  human_intervention_required boolean not null default true,
  reason                      text,
  suggested_reply             text,
  suggested_action            text,
  status                      text not null default 'open',   -- open | resolved
  metadata                    jsonb default '{}'::jsonb,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now(),
  resolved_at        timestamptz
);
create index if not exists idx_agent_flags_conversation on agent_flags (conversation_id);
create index if not exists idx_agent_flags_status on agent_flags (status);
create index if not exists idx_agent_flags_type on agent_flags (flag_type);
create index if not exists idx_agent_flags_seed_batch on agent_flags (seed_batch_id);

-- ---------------------------------------------------------------------
-- human_takeovers
-- ---------------------------------------------------------------------
create table if not exists human_takeovers (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references conversations (id) on delete cascade,
  operator_name    text,
  status           text not null default 'active',   -- active | ended
  started_at       timestamptz not null default now(),
  ended_at         timestamptz,
  notes            text,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false
);
create index if not exists idx_human_takeovers_conversation on human_takeovers (conversation_id);
create index if not exists idx_human_takeovers_status on human_takeovers (status);
create index if not exists idx_human_takeovers_seed_batch on human_takeovers (seed_batch_id);

-- ---------------------------------------------------------------------
-- approval_queue
-- ---------------------------------------------------------------------
create table if not exists approval_queue (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid references conversations (id) on delete cascade,
  message_id       uuid references messages (id) on delete set null,
  approval_type    text not null default 'whatsapp_reply',
  draft_text       text,
  edited_text      text,
  status           text not null default 'pending',   -- pending | approved | rejected
  requested_by     text,
  approved_by      text,
  rejected_by      text,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now(),
  resolved_at        timestamptz
);
create index if not exists idx_approval_queue_status on approval_queue (status);
create index if not exists idx_approval_queue_conversation on approval_queue (conversation_id);
create index if not exists idx_approval_queue_seed_batch on approval_queue (seed_batch_id);

-- ---------------------------------------------------------------------
-- tickets
-- ---------------------------------------------------------------------
create table if not exists tickets (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid references conversations (id) on delete set null,
  order_id         uuid references orders (id) on delete set null,
  ticket_type      text,
  priority         text,
  assigned_team    text,
  status           text not null default 'open',
  title            text,
  description      text,
  -- test-data markers
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
create index if not exists idx_tickets_status on tickets (status);
create index if not exists idx_tickets_priority on tickets (priority);
create index if not exists idx_tickets_seed_batch on tickets (seed_batch_id);

-- ---------------------------------------------------------------------
-- agent_logs
-- ---------------------------------------------------------------------
create table if not exists agent_logs (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid references conversations (id) on delete set null,
  action           text not null,
  input_json       jsonb default '{}'::jsonb,
  output_json      jsonb default '{}'::jsonb,
  domain           text,
  handoff          boolean not null default false,
  llm_mode         text default 'mock',
  whatsapp_mode    text default 'mock',
  safe_for_demo    boolean not null default true,
  -- test-data markers
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_batch_id      text,
  seed_source        text,
  test_scenario_id   text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now()
);
create index if not exists idx_agent_logs_conversation on agent_logs (conversation_id, created_at);
create index if not exists idx_agent_logs_action on agent_logs (action);
create index if not exists idx_agent_logs_seed_batch on agent_logs (seed_batch_id);

-- ---------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------
drop trigger if exists trg_customers_updated_at on customers;
create trigger trg_customers_updated_at before update on customers
  for each row execute function set_updated_at();

drop trigger if exists trg_conversations_updated_at on conversations;
create trigger trg_conversations_updated_at before update on conversations
  for each row execute function set_updated_at();

drop trigger if exists trg_orders_updated_at on orders;
create trigger trg_orders_updated_at before update on orders
  for each row execute function set_updated_at();

drop trigger if exists trg_tickets_updated_at on tickets;
create trigger trg_tickets_updated_at before update on tickets
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- Row Level Security — dev/test posture
-- Enable RLS on every table with NO anon/authenticated policies. This denies
-- the public PostgREST surface by default. The FastAPI backend uses the
-- service role over a direct Postgres connection (bypasses RLS). The frontend
-- must go through FastAPI, never Supabase directly. Production RLS is designed
-- later in the production project.
-- ---------------------------------------------------------------------
alter table customers        enable row level security;
alter table conversations    enable row level security;
alter table messages         enable row level security;
alter table orders           enable row level security;
alter table order_events     enable row level security;
alter table agent_flags      enable row level security;
alter table human_takeovers  enable row level security;
alter table approval_queue   enable row level security;
alter table tickets          enable row level security;
alter table agent_logs       enable row level security;
