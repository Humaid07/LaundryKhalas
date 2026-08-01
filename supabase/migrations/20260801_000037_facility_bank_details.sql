-- =====================================================================
-- LaundryKhalas — Facility bank details (encrypted payout banking)
-- Migration: 20260801_000037_facility_bank_details
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- One bank-details row per facility (payout banking a partner enters and an
-- authorized internal user can view/edit). This data is SENSITIVE:
--   * The two account-identifying values — IBAN and account number — are stored
--     ONLY as ciphertext (Fernet, services/field_encryption.py). The DB never
--     holds their plaintext. A ``*_last4`` column is kept alongside so the API
--     can render a masked display (AE•• •••• •••• •••• 1234) WITHOUT decrypting.
--   * Non-secret descriptive fields (holder name, bank name, SWIFT/BIC, branch,
--     country, currency) are stored in the clear — they identify a bank, not an
--     account, and are needed for display.
--   * Every read/write is scoped to the caller's facility (facility_id resolved
--     from the authenticated session, never a client-supplied id). The service
--     role bypasses RLS, so isolation is enforced in application SQL; the RLS
--     deny policy is a belt-and-suspenders block on the public PostgREST roles.
--   * Audit (facility_audit_log) records ONLY masked identifiers (iban_last4),
--     never ciphertext or plaintext (CLAUDE.md §7/§10).
--
-- Additive + idempotent (safe to run more than once).
--
-- Rollback:
--   drop policy if exists facility_bank_details_no_public_access on facility_bank_details;
--   drop table if exists facility_bank_details;
-- =====================================================================

create table if not exists facility_bank_details (
    id                       uuid primary key default gen_random_uuid(),
    facility_id              uuid not null unique references facilities(id) on delete cascade,
    -- descriptive (non-secret) fields
    account_holder_name      text,
    bank_name                text,
    swift_bic                text,
    branch_name              text,
    bank_country             text not null default 'AE',   -- ISO-3166 alpha-2
    currency                 text not null default 'AED',   -- ISO-4217
    -- sensitive fields: ciphertext only (plaintext is NEVER stored) + last-4 for
    -- masked display so reads don't need to decrypt.
    iban_ciphertext          text,
    iban_last4               text,
    account_number_ciphertext text,
    account_number_last4     text,
    -- provenance
    created_by_user_id       uuid,
    updated_by_user_id       uuid,
    -- standard test-data marker columns
    is_test_data             boolean not null default false,
    is_demo                  boolean not null default false,
    environment              text    not null default 'dev',
    seed_batch_id            text,
    seed_source              text,
    test_scenario_id         text,
    created_by_seed          boolean not null default false,
    created_at               timestamptz not null default now(),
    updated_at               timestamptz not null default now()
);

create index if not exists idx_facility_bank_details_facility
    on facility_bank_details (facility_id);

drop trigger if exists set_facility_bank_details_updated_at on facility_bank_details;
create trigger set_facility_bank_details_updated_at before update on facility_bank_details
    for each row execute function set_updated_at();

-- RLS: deny the public PostgREST roles; the backend service role bypasses RLS
-- and is the only reader/writer (mirrors facility_audit_log / order_photos).
alter table facility_bank_details enable row level security;
revoke all on facility_bank_details from anon, authenticated;
drop policy if exists facility_bank_details_no_public_access on facility_bank_details;
create policy facility_bank_details_no_public_access on facility_bank_details
    as restrictive for all to anon, authenticated
    using (false) with check (false);
