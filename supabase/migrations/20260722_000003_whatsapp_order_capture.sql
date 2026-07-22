-- =====================================================================
-- LaundryKhalas — WhatsApp order-capture additive columns
-- Migration: 20260722_000003_whatsapp_order_capture
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds the two operational-detail columns the WhatsApp order-capture flow
-- needs to persist a full pickup address:
--   * customers.address     — the customer's pickup/home address (BACKEND-ONLY;
--                             never returned by broad list APIs / dashboard
--                             tables, which show area/city only — CLAUDE.md §7).
--   * orders.pickup_address — the per-order pickup address (exposed only in the
--                             secure single-order detail endpoint, never in the
--                             /api/orders list responses).
--
-- Both are additive and nullable, so this migration is safe to run on top of
-- 20260721_000001 without touching any existing row or the RLS posture.
-- =====================================================================

alter table customers add column if not exists address text;
alter table orders    add column if not exists pickup_address text;
