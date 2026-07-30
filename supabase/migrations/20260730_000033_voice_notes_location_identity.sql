-- =====================================================================
-- LaundryKhalas — Voice handling, structured order notes, location pin,
--                 customer identity, and facility-handoff state
-- Migration: 20260730_000033_voice_notes_location_identity
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds the durable state required by the WhatsApp-agent enhancement:
--   * conversations: unprocessable-voice-note escalation counters (survive
--     restarts/retries; counted by unique Evolution message id).
--   * orders: structured pickup-address fields, location-pin capture metadata,
--     confirmed-notes snapshot, and facility-handoff status.
--   * customers: WhatsApp number + profile-name identity fields with source /
--     confidence / verification (backend stays authoritative).
--   * order_notes: NEW structured, categorized, de-duplicated additional-notes
--     table (replaces the single free-text pickup_instruction_text as the
--     authoritative note store; the old columns are left intact for back-compat).
--
-- Design notes:
--   * All additive `add column if not exists` / `create table if not exists`.
--   * order_notes carries a dedupe_key + partial-unique index so duplicate
--     webhooks / repeated instructions / regenerated summaries cannot create
--     duplicate ACTIVE notes.
--   * category is CHECK-constrained to the approved vocabulary.
--   * RLS: deny anon/authenticated (service role — the backend — bypasses),
--     matching users/orders/order_photos posture.
--   * No latitude/longitude is ever invented here; columns are nullable and only
--     written from a real Evolution location event or an approved geocode.
--
-- Additive + idempotent (safe to run more than once).
--
-- Rollback:
--   drop policy if exists order_notes_no_public_access on order_notes;
--   drop table if exists order_notes;
--   -- (added columns on conversations/orders/customers are additive and may be
--   --  left in place; drop individually if a full revert is required.)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. conversations — unprocessable-voice-note escalation state
-- ---------------------------------------------------------------------
alter table conversations add column if not exists unprocessed_voice_message_count integer not null default 0;
alter table conversations add column if not exists last_unprocessed_voice_message_id text;
alter table conversations add column if not exists last_unprocessed_voice_message_at timestamptz;
alter table conversations add column if not exists voice_text_fallback_sent_at timestamptz;
-- none | fallback_sent | escalated
alter table conversations add column if not exists voice_escalation_status text not null default 'none';

-- ---------------------------------------------------------------------
-- 2. orders — structured address, location-pin capture, notes snapshot,
--            facility-handoff status
-- ---------------------------------------------------------------------
-- Structured, human-readable pickup address parts (pickup_address free text
-- and pickup_latitude/pickup_longitude/address_source already exist).
alter table orders add column if not exists building_name text;
alter table orders add column if not exists villa_number text;
alter table orders add column if not exists apartment_number text;
alter table orders add column if not exists floor text;
alter table orders add column if not exists room_number text;
alter table orders add column if not exists landmark text;
alter table orders add column if not exists access_details text;

-- Location-pin capture metadata (coordinates live in pickup_latitude/longitude).
alter table orders add column if not exists location_source text;          -- whatsapp_pin | geocoded | operations
alter table orders add column if not exists location_type text;            -- static | live
alter table orders add column if not exists location_name text;
alter table orders add column if not exists location_provider_address text;
alter table orders add column if not exists location_message_id text;
alter table orders add column if not exists location_received_at timestamptz;
alter table orders add column if not exists location_accuracy double precision;
-- received | missing | manual_review
alter table orders add column if not exists location_pin_status text not null default 'missing';

-- Immutable snapshot of notes at the moment of confirmation.
alter table orders add column if not exists confirmed_notes_snapshot jsonb;
alter table orders add column if not exists notes_confirmed_at timestamptz;

-- Facility handoff status (the payload itself is derived on demand by the
-- serializer; we persist status + a redacted copy for audit/history).
alter table orders add column if not exists facility_handoff_status text;    -- pending | sent | failed
alter table orders add column if not exists facility_handoff_at timestamptz;
alter table orders add column if not exists facility_handoff_attempts integer not null default 0;
alter table orders add column if not exists facility_handoff_last_error text;
alter table orders add column if not exists facility_handoff_payload jsonb;   -- redacted snapshot of what was shared

-- ---------------------------------------------------------------------
-- 3. customers — WhatsApp number + profile-name identity
-- ---------------------------------------------------------------------
alter table customers add column if not exists whatsapp_number text;
alter table customers add column if not exists normalized_contact_number text;
alter table customers add column if not exists contact_number_source text;      -- WHATSAPP_SENDER | CUSTOMER_PROVIDED | OPERATIONS
alter table customers add column if not exists contact_number_verified boolean not null default false;
alter table customers add column if not exists whatsapp_profile_name text;
alter table customers add column if not exists customer_name text;
alter table customers add column if not exists customer_name_source text;       -- CUSTOMER_PROVIDED | CONFIRMED | WHATSAPP_PROFILE | UNKNOWN
alter table customers add column if not exists customer_name_confidence numeric(4,3);
alter table customers add column if not exists customer_name_requires_confirmation boolean not null default false;

-- ---------------------------------------------------------------------
-- 4. order_notes — structured additional-notes store
-- ---------------------------------------------------------------------
create table if not exists order_notes (
  id                 uuid primary key default gen_random_uuid(),
  order_id           uuid not null references orders (id) on delete cascade,
  conversation_id    uuid references conversations (id) on delete set null,
  category           text not null,
  text               text not null,
  source             text not null default 'CUSTOMER_MESSAGE',   -- CUSTOMER_MESSAGE | AGENT | OPERATIONS | SYSTEM
  source_message_id  text,
  confidence         numeric(4,3),
  status             text not null default 'ACTIVE',             -- ACTIVE | REMOVED | SUPERSEDED
  customer_confirmed boolean not null default false,
  is_amendment       boolean not null default false,            -- captured after order confirmation
  dedupe_key         text not null,                             -- sha1(order_id|category|normalized_text)
  superseded_by      uuid references order_notes (id) on delete set null,
  -- test-data markers (repo convention)
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

-- Category vocabulary guard (idempotent add).
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'order_notes_category_check') then
    alter table order_notes add constraint order_notes_category_check check (category in (
      'PICKUP_INSTRUCTION','DELIVERY_INSTRUCTION','ACCESS_INSTRUCTION','CONTACT_PREFERENCE',
      'TIMING_PREFERENCE','ITEM_HANDLING','STAIN_NOTE','EXISTING_DAMAGE','SPECIAL_CARE',
      'FACILITY_INSTRUCTION','INSPECTION_REQUIREMENT','OTHER_OPERATIONAL_NOTE'
    ));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'order_notes_status_check') then
    alter table order_notes add constraint order_notes_status_check check (status in ('ACTIVE','REMOVED','SUPERSEDED'));
  end if;
end $$;

create index if not exists idx_order_notes_order on order_notes (order_id);
create index if not exists idx_order_notes_order_status on order_notes (order_id, status);
-- Prevents duplicate ACTIVE notes (same normalized instruction) on an order.
create unique index if not exists uq_order_notes_active_dedupe
  on order_notes (order_id, dedupe_key) where status = 'ACTIVE';

-- RLS: backend (service role) only; deny anon/authenticated like other business tables.
alter table order_notes enable row level security;
revoke all on order_notes from anon, authenticated;
drop policy if exists order_notes_no_public_access on order_notes;
create policy order_notes_no_public_access on order_notes
  as restrictive for all to anon, authenticated using (false) with check (false);
