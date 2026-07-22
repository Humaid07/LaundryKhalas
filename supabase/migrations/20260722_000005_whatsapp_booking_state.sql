-- =====================================================================
-- LaundryKhalas — WhatsApp laundry pickup BOOKING STATE MACHINE
-- Migration: 20260722_000005_whatsapp_booking_state
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Turns the WhatsApp draft order into an explicit, persisted booking state
-- machine (DB is the source of truth for the current step — the LLM may never
-- skip a state). Adds:
--   1. Booking-state + structured pickup columns on `orders` (the open draft IS
--      the booking; no parallel `bookings` table — reuses the existing row).
--   2. `messages.wa_message_id` + a unique index for webhook idempotency (a
--      redelivered Evolution event must not create a duplicate message, advance
--      the state twice, or confirm an order twice).
--   3. A DB-backed `pickup_slots` catalogue + availability model (capacity /
--      weekday / emirate / service scoping) so the agent NEVER invents a slot.
--
-- Everything is additive + idempotent (add column/table/index if not exists,
-- on conflict do nothing), so it is safe on top of 000001–000004 without
-- touching existing rows or the RLS posture.
-- =====================================================================

-- 1) Booking state machine + structured pickup fields on the draft order --------
alter table orders add column if not exists conversation_state      text;      -- FSM state
alter table orders add column if not exists service_name_snapshot   text;      -- label at selection time
alter table orders add column if not exists pickup_date             date;      -- normalized, never past
alter table orders add column if not exists pickup_slot_id          text;      -- -> pickup_slots.slot_id
alter table orders add column if not exists pickup_area             text;      -- captured pickup area (never inferred)
alter table orders add column if not exists pickup_start_time       timestamptz;
alter table orders add column if not exists pickup_end_time         timestamptz;
alter table orders add column if not exists pickup_emirate          text;
alter table orders add column if not exists pickup_latitude         double precision;
alter table orders add column if not exists pickup_longitude        double precision;
alter table orders add column if not exists address_source          text;      -- typed | whatsapp_location | saved
alter table orders add column if not exists pickup_instruction_code text;      -- e.g. pickup_from_reception
alter table orders add column if not exists pickup_instruction_text text;      -- free-text / snapshot
alter table orders add column if not exists service_selected_at     timestamptz;
alter table orders add column if not exists confirmed_at            timestamptz;

-- 2) Webhook idempotency -------------------------------------------------------
alter table messages add column if not exists wa_message_id text;
create unique index if not exists messages_wa_message_id_key
    on messages (wa_message_id) where wa_message_id is not null;

-- 3) Pickup-slot catalogue + availability --------------------------------------
create table if not exists pickup_slots (
    id            uuid primary key default gen_random_uuid(),
    slot_id       text unique not null,     -- stable id, e.g. 'morning_08_11'
    label         text not null,            -- '8:00 AM – 11:00 AM'
    start_time    time not null,
    end_time      time not null,
    weekdays      int[] not null default '{0,1,2,3,4,5,6}',  -- Postgres dow: 0=Sun .. 6=Sat
    emirate       text,                      -- null = available in every emirate
    service_id    text,                      -- null = available for every service
    capacity      int  not null default 20,  -- max confirmed bookings per (date, slot)
    active        boolean not null default true,
    sort_order    int  not null default 0,
    is_test_data  boolean not null default true,
    is_demo       boolean not null default false,
    environment   text not null default 'dev',
    seed_batch_id text,
    seed_source   text,
    created_by_seed boolean not null default false,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
create index if not exists pickup_slots_active_idx on pickup_slots(active);
create index if not exists orders_pickup_date_slot_idx on orders(pickup_date, pickup_slot_id);

alter table pickup_slots enable row level security;

drop trigger if exists set_pickup_slots_updated_at on pickup_slots;
create trigger set_pickup_slots_updated_at before update on pickup_slots
    for each row execute function set_updated_at();

-- Default operating slots (idempotent). These are the ONLY bookable windows;
-- the agent reads them from here and offers only the ones available for the day.
insert into pickup_slots (slot_id, label, start_time, end_time, sort_order, created_by_seed, is_test_data, environment)
values
  ('morning_08_11',   '8:00 AM – 11:00 AM',  '08:00', '11:00', 1, true, true, 'dev'),
  ('midday_11_14',    '11:00 AM – 2:00 PM',  '11:00', '14:00', 2, true, true, 'dev'),
  ('afternoon_14_17', '2:00 PM – 5:00 PM',   '14:00', '17:00', 3, true, true, 'dev'),
  ('evening_17_20',   '5:00 PM – 8:00 PM',   '17:00', '20:00', 4, true, true, 'dev'),
  ('night_20_22',     '8:00 PM – 10:00 PM',  '20:00', '22:00', 5, true, true, 'dev')
on conflict (slot_id) do nothing;
