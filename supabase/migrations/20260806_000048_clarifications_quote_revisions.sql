-- =====================================================================
-- LaundryKhalas — Clarification amendments + facility quote revisions
-- Migration: 20260806_000048_clarifications_quote_revisions
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
--   * order_notes: item + issue linkage so a customer's CLARIFICATION ANSWER can
--     be stored as an amendment tied to the affected item + the facility issue
--     that raised it (never overwriting the original confirmed instruction).
--       - order_item_id     (affected line item; null = whole order)
--       - facility_issue_id (the issue whose clarification this answers)
--   * facility_quote_revisions: NEW table for the revised-quote workflow. The
--     facility proposes a fee for out-of-standard work; Operations reviews; the
--     BACKEND computes the customer-facing price from the approved margin rule
--     (never the LLM, never exposing facility fee/margin to the customer); the
--     customer must approve before the affected work continues.
--
-- Additive + idempotent.
--
-- Rollback:
--   alter table order_notes drop column if exists order_item_id;
--   alter table order_notes drop column if exists facility_issue_id;
--   drop policy if exists facility_quote_revisions_no_public_access on facility_quote_revisions;
--   drop table if exists facility_quote_revisions;
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. order_notes — item + issue linkage (for clarification amendments)
-- ---------------------------------------------------------------------
alter table order_notes add column if not exists order_item_id text;
alter table order_notes add column if not exists facility_issue_id uuid;

create index if not exists idx_order_notes_issue on order_notes (facility_issue_id) where facility_issue_id is not null;

-- ---------------------------------------------------------------------
-- 2. facility_quote_revisions — revised-fee workflow
-- ---------------------------------------------------------------------
create table if not exists facility_quote_revisions (
  id                 uuid primary key default gen_random_uuid(),
  order_id           uuid not null references orders (id) on delete cascade,
  order_item_id      text,
  facility_id        uuid not null,
  facility_issue_id  uuid references facility_issues (id) on delete set null,
  -- The facility's proposed fee (internal). customer_price is derived by the
  -- backend on Operations approval and is the ONLY figure shown to the customer.
  facility_fee       numeric(12,2) not null,
  currency           text not null default 'AED',
  reason             text,
  customer_price     numeric(12,2),
  status             text not null default 'pending_ops_review'
                     check (status in ('pending_ops_review','ops_approved','customer_pending',
                                       'customer_approved','ops_rejected','customer_rejected')),
  created_by_user_id uuid,
  created_by_label   text,
  reviewed_by        text,
  reviewed_at        timestamptz,
  customer_decided_at timestamptz,
  -- test-data markers (repo convention)
  is_test_data       boolean not null default false,
  is_demo            boolean not null default false,
  environment        text    not null default 'dev',
  seed_source        text,
  created_by_seed    boolean not null default false,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_facility_quote_revisions_order on facility_quote_revisions (order_id);
create index if not exists idx_facility_quote_revisions_status on facility_quote_revisions (status);

alter table facility_quote_revisions enable row level security;
revoke all on facility_quote_revisions from anon, authenticated;
drop policy if exists facility_quote_revisions_no_public_access on facility_quote_revisions;
create policy facility_quote_revisions_no_public_access on facility_quote_revisions
  as restrictive for all to anon, authenticated using (false) with check (false);
