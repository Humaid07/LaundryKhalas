-- =====================================================================
-- LaundryKhalas — service-taxonomy columns on WhatsApp-captured orders
-- Migration: 20260722_000004_service_taxonomy
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds the canonical service-taxonomy columns so a WhatsApp-created order stores
-- the structured service selection (matching the live LaundryKhalas catalog in
-- apps/whatsapp-agent/config/laundry_services.json), not just a free-text label:
--   * orders.service_id            — canonical service id, e.g. 'boutique_clean_press'.
--   * orders.service_display_name  — display label, e.g. 'Boutique Clean & Press'.
--                                    (The pre-existing `service` column is kept as
--                                    the back-compat label mirror.)
--   * orders.unit_type             — bag | item | pair | set | sqm (from the catalog).
--   * orders.requires_manual_quote — true for services priced only after
--                                    inspection/measurement (bag spa, tailoring,
--                                    carpet/curtain); the agent must NOT invent a
--                                    total for these (CLAUDE.md RULE 7/8). The
--                                    estimated price continues to live in `amount`.
--
-- All additive and nullable, so this is safe to run on top of
-- 20260722_000003 without touching any existing row or the RLS posture.
-- =====================================================================

alter table orders add column if not exists service_id            text;
alter table orders add column if not exists service_display_name  text;
alter table orders add column if not exists unit_type             text;
alter table orders add column if not exists requires_manual_quote boolean not null default false;
