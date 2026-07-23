# Presentation Notes — Real Price List, Item Catalogue & VAT Quoting

**Date:** 2026-07-23 · Related: [[2026-07-23-service-catalogue-pricing]]

## What we can show
- The **real Laundry Khalas price list** is now in the system: 9 categories,
  120 individually-priced items, transcribed and verified from the approved image.
- On WhatsApp, the agent asks for a **category → item → quantity**, then shows a
  **priced summary with 5% VAT** and a running total.
- The **database is the source of truth** — 120 items live in Supabase, and an
  automatic parity check confirms the app, agent and DB all agree.

## Suggested demo flow
1. Show the price-list image, then `GET /api/catalogue/categories` (9 real
   categories) and `GET /api/catalogue/items?category=CLEAN_PRESS`.
2. `POST /api/catalogue/quote` with `3 × Shirt` + `2 × Trousers` →
   **Subtotal AED 49, VAT AED 2.45, Total AED 51.45.**
3. Show a "From" item (Sports Sneakers) → the quote says **"from AED 50 per pair,
   final price after inspection"** and does **not** invent a total.
4. Show the confirmation summary the customer sees on WhatsApp (line items + VAT).

## Talking points
- **No invented prices.** Bold price = the active price; the crossed-out number is
  stored separately as the previous price and never charged. "From" prices are
  never turned into a guaranteed total — they wait for inspection.
- **VAT done correctly.** Prices exclude 5% VAT; VAT is added only to the firm
  part of the order and the total is clearly labelled "estimated" when anything is
  pending measurement or inspection.
- **Frozen order pricing.** Once an order is placed, its line items and prices are
  snapshotted — changing the catalogue later never re-prices a past order.
- **Tested.** 372 automated tests pass, including all 24 required pricing checks.

## Business value
Accurate, on-brand quoting on WhatsApp with correct VAT — the foundation for real
customer orders and finance reporting.

## Honest caveats
- The general "what services do you offer" chit-chat + SEO pages still reference
  the older marketing service names; the **booking/pricing/orders** path uses the
  new real catalogue. Aligning the informational side is the next step.
- Line-item pricing shows in the Orders drawer today; the standalone order-detail
  page picks it up when fed live order data.

## What's coming next
Align the informational/SEO taxonomy to the 9 real categories, then a live
two-number WhatsApp test of the full item → quote → confirm flow.
