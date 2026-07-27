-- =====================================================================
-- LaundryKhalas — PUBLISHED PRICES ARE ALREADY VAT-INCLUSIVE
-- Migration: 20260727_000011_prices_vat_inclusive
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Corrects the earlier "prices EXCLUDE 5% VAT" assumption. Every published
-- Laundry Khalas price (website, approved price-list image, admin Pricing
-- Management, published catalogue versions) is ALREADY a final, VAT-inclusive
-- customer price. The customer pays the stored price with NO 5% added on top
-- (task spec §§1-4). This flips the `prices_include_vat` flag so the price
-- resolver / public pricing API stop multiplying published prices by 1.05.
--
-- Additive + idempotent. Historical CONFIRMED orders are DELIBERATELY left
-- untouched — their frozen pricing snapshot is immutable (spec §11); only the
-- live catalogue's tax-treatment flag changes.
-- =====================================================================

-- 1) Published catalogue version items are already final customer prices -------
alter table catalogue_version_items
    alter column prices_include_vat set default true;

update catalogue_version_items
   set prices_include_vat = true
 where prices_include_vat is distinct from true;

-- 2) New orders default to VAT-inclusive pricing. The orders table has no
--    prices_include_vat column (the app reads the flag as inclusive-by-default
--    in db/repositories/orders_repo.py); this comment documents the contract.
--    Historical orders keep their stored subtotal/vat/estimated_total snapshot
--    exactly as written — they are NOT recomputed (spec §11).

comment on column catalogue_version_items.prices_include_vat is
    'TRUE: current_price/regular_price are already final VAT-inclusive customer '
    'prices; no 5% is added on top (task spec §§1-4).';
