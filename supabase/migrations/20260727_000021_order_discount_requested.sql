-- =====================================================================
-- LaundryKhalas — DISCOUNT-REQUESTED FLAG (20%-over-200 tier)
-- Migration: 20260727_000021_order_discount_requested
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds the sticky per-order flag recording that the customer explicitly asked
-- for a discount ("can you make it cheaper", "best rate", "that's expensive").
-- It gates the higher automatic discount tier: an exact pre-discount order value
-- strictly over AED 200 WITH a discount request gets 20% (else the >AED 100 15%
-- tier, else none — the tiers never stack). Deterministic + snapshotted with the
-- order so a rule change never alters a confirmed order (spec §11).
--
-- Additive + idempotent.
-- =====================================================================

alter table orders add column if not exists discount_requested boolean not null default false;

comment on column orders.discount_requested is
    'Customer explicitly asked for a discount on THIS order — gates the '
    '20%-over-AED-200 discount tier (task spec discount precedence).';
