-- =====================================================================
-- LaundryKhalas — Structured facility-issue fields (item link, flags, photos)
-- Migration: 20260806_000047_facility_issue_structured_fields
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Extends facility_issues (mig 000018) so a facility can raise a precise,
-- item-scoped issue that Operations can action:
--   * order_item_id            — the affected line item (null = whole order)
--   * requires_customer_response, requires_photo, requires_price_revision
--     — derived from the canonical issue-type registry (services/facility_issue_types.py)
--   * photo_ids (jsonb)        — order_photos ids attached as evidence
--       (photos live in the unified order_photos table with source=FACILITY_ISSUE;
--        this is just the list of ids attached to THIS issue).
--
-- issue_type stays free text at the DB layer (validated in the app against the
-- registry) so legacy rows keep working.
--
-- Additive + idempotent.
--
-- Rollback:
--   alter table facility_issues drop column if exists order_item_id;
--   alter table facility_issues drop column if exists requires_customer_response;
--   alter table facility_issues drop column if exists requires_photo;
--   alter table facility_issues drop column if exists requires_price_revision;
--   alter table facility_issues drop column if exists photo_ids;
-- =====================================================================

alter table facility_issues add column if not exists order_item_id text;
alter table facility_issues add column if not exists requires_customer_response boolean not null default false;
alter table facility_issues add column if not exists requires_photo boolean not null default false;
alter table facility_issues add column if not exists requires_price_revision boolean not null default false;
alter table facility_issues add column if not exists photo_ids jsonb not null default '[]'::jsonb;

create index if not exists facility_issues_order_idx on facility_issues (order_id) where order_id is not null;
