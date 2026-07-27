-- =====================================================================
-- LaundryKhalas — AUTOMATIC ORDER-LEVEL DISCOUNT SNAPSHOT
-- Migration: 20260727_000012_order_discount
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds an immutable per-order snapshot of the automatic order-level discount
-- (task spec §§5-11). The discount RULE itself (threshold AED 100, 15%,
-- strictly-greater-than) is centrally configurable in
-- config/order_discounts.json and resolved by services/discount.py — the DB
-- stores only the applied snapshot so a confirmed order's total is immutable
-- even if the rule later changes (spec §11).
--
-- Money model: `estimated_total`/`amount` remain the FINAL amount the customer
-- pays (already net of this discount). `eligible_subtotal` is the pre-discount
-- sum of final VAT-inclusive line totals; `discount_amount` = eligible_subtotal
-- - estimated_total when the order qualified, else 0/null.
--
-- Additive + idempotent (add column if not exists). No existing rows change.
-- =====================================================================

alter table orders add column if not exists eligible_subtotal    numeric(12,2); -- pre-discount subtotal (final, incl.)
alter table orders add column if not exists discount_rule_code   text;          -- e.g. ORDER_OVER_100_DISCOUNT
alter table orders add column if not exists discount_percentage  numeric(6,2);  -- snapshot, e.g. 15.00
alter table orders add column if not exists discount_threshold   numeric(12,2); -- snapshot, e.g. 100.00
alter table orders add column if not exists discount_amount      numeric(12,2); -- eligible_subtotal - final total

comment on column orders.discount_amount is
    'Automatic order-discount applied to THIS order (spec §§5-11). Immutable '
    'snapshot; estimated_total/amount are already net of it.';
