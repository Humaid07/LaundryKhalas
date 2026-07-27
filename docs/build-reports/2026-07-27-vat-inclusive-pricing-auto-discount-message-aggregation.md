# Build Report — VAT-Inclusive Pricing, Automatic 15% Discount & WhatsApp Message Aggregation

**Date:** 2026-07-27
**Author:** Engineering (Claude)
**Status:** Backend complete + tested (SQLite hermetic suite). Live WhatsApp/Supabase paths need manual smoke verification.

---

## 1. Task objective

Three corrections to the WhatsApp agent, pricing engine, order workflow and Anthropic integration:

1. **Published prices are already VAT-inclusive** — stop adding 5% on top. AED 60 → AED 60 (was wrongly AED 63).
2. **Automatic 15% order discount** when the eligible order subtotal is **strictly greater than AED 100**.
3. **Smart broken-message aggregation** — buffer rapid customer fragments into ONE logical turn → ONE Anthropic call → ONE reply.

## 2. What was built (summary)

- **Pillar A — VAT-inclusive:** flipped the single tax-treatment flag so every price surface shows the published price unchanged; no code path multiplies by 1.05 anymore. Frontend Pricing Management preview corrected.
- **Pillar B — Auto discount:** a central, config-driven discount rule + a pure Decimal engine, integrated once into the quote so it flows to the WhatsApp summary, order snapshot, dashboard and (future) Stripe — applied exactly once, never on unknown/inspection totals.
- **Pillar C — Message aggregation:** a durable `conversation_turns` model + a pure aggregation core + an in-process per-conversation debounce/lock/flush service + startup recovery, integrated into the Evolution webhook behind a config flag (default on).

## 3. Why

- The previous "final pricing" work (2026-07-26) had stored catalogue prices as **pre-VAT** and derived `final = base × 1.05` — i.e. it was applying the very double-VAT this task removes. Website/approved prices are already final customer prices.
- The business wants an automatic loyalty-style discount over AED 100.
- Customers type in bursts; replying to every fragment produced multiple confusing replies and premature clarifying questions.

## 4. Root cause of the double-VAT

`services/money.final_unit_price()` multiplied `base × (1 + vat_rate)` whenever `prices_include_vat` was False, and **every** config/model/DB default set that flag to **False**. All customer-facing surfaces already routed through this one function, so a single flag flip corrects the whole system. (The admin frontend additionally re-implemented `CUSTOMER_PRICE_MULTIPLIER = 1.05` client-side — also removed.)

## 5. Files created

- `apps/whatsapp-agent/config/order_discounts.json` — central discount-rule config (ORDER_OVER_100_DISCOUNT).
- `apps/whatsapp-agent/services/discount.py` — pure Decimal discount engine.
- `apps/whatsapp-agent/services/message_aggregation.py` — pure combine + flush-decision logic.
- `apps/whatsapp-agent/services/turn_service.py` — `TurnBuffer`: per-conversation debounce timer, conversation lock, flush, restart recovery.
- `apps/whatsapp-agent/db/repositories/turns_repo.py` — durable `conversation_turns` repo (asyncpg).
- `apps/whatsapp-agent/tests/test_order_discount.py` — 18 discount tests.
- `apps/whatsapp-agent/tests/test_message_aggregation.py` — 13 pure-core tests.
- `apps/whatsapp-agent/tests/test_turn_service.py` — 8 buffer-orchestration tests.
- `supabase/migrations/20260727_000011_prices_vat_inclusive.sql`
- `supabase/migrations/20260727_000012_order_discount.sql`
- `supabase/migrations/20260727_000013_conversation_turns.sql`

## 6. Files modified

- `services/money.py` — default `prices_include_vat=True`; docstrings.
- `services/pricing.py` — Quote carries discount fields; `calculate_estimate` computes the discount once; `format_quote_summary` shows the discount block; docstrings.
- `services/catalogue.py` — docstring/example (60 stays 60).
- `services/booking_flow.py` — `_pricing_updates` writes the discount snapshot; edit-service reset clears discount fields.
- `config/laundry_catalogue.json` — `prices_include_vat: true` + note.
- `models.py` — `CatalogueItem.prices_include_vat` default True.
- `db/repositories/orders_repo.py` — `_pricing_block` reads inclusive + surfaces discount; `_BOOKING_COLS` allows discount columns.
- `agents/whatsapp_agent/booking_tools.py` — `get_order_summary` returns discount info; prompt guidance (no VAT, discount over 100, inclusive examples).
- `agents/whatsapp_agent/llm_tools.py` — price guidance (inclusive, discount).
- `api/evolution_webhooks.py` — extracted `_process_reply` per-turn processor; buffer dispatch + turn recovery; confirmation text shows the discount; fragment metadata stores location.
- `settings.py` — aggregation env vars.
- `main.py` — startup turn recovery (supabase-only, best-effort).
- `.env.example` — aggregation vars.
- Tests updated to VAT-inclusive expectations: `test_final_pricing.py`, `test_catalogue_pricing.py`, `test_pricing_management.py`, `test_item_booking_flow.py`.
- `apps/admin/components/dashboard/operations/pricing/PricingManagement.tsx` — removed client-side ×1.05; table/preview now consistent; admin note reworded.

## 7. API endpoints added/changed

- No new routes. `GET /api/public/pricing` and the orders/pricing responses now return already-final prices and a discount block (`discount_applied`, `discount_amount`, `discount_percentage`, `eligible_subtotal`). The Evolution webhook (`POST /webhooks/evolution`) now aggregates fragments into turns.

## 8. Database changes

- `catalogue_version_items.prices_include_vat` → default true + existing rows updated (000011).
- `orders` → new immutable discount snapshot columns: `eligible_subtotal`, `discount_rule_code`, `discount_percentage`, `discount_threshold`, `discount_amount` (000012).
- New `conversation_turns` table + `messages.turn_id` (000013).

## 9. Agent behavior changes

- Quotes/summaries show the **published price unchanged** (no 5%) and **no VAT wording**.
- Orders over AED 100 automatically show `Subtotal / Automatic 15% discount / Final price`.
- Starting-price/inspection orders never get a guaranteed discounted total — the agent may say the 15% applies automatically *if* the confirmed order exceeds AED 100.
- Rapid fragments are combined; the agent waits for a short lull, then answers once.

## 10. What is mock-only / not live

- **No Stripe exists** anywhere in the repo (confirmed by audit) — payment is mock/off. The discount flows into the single `estimated_total`/`amount` the customer pays, which is what any future Stripe integration must charge. No Stripe code was added.
- The admin **discount-rule editing UI** (spec §12) was **deferred** — the rule is fully centrally configurable via `config/order_discounts.json`. Read/write via the dashboard is a follow-up.

## 11. Tests run & results

- Full hermetic backend suite (SQLite): **536 passed, 0 failed** (was 493). New: 18 discount + 13 aggregation-core + 8 turn-service = 39 new tests. Updated ~30 pricing assertions to VAT-inclusive values.
- Frontend `apps/admin`: `tsc --noEmit` clean after the Pricing Management change.

## 12. Known limitations / honest caveats

- **The Evolution webhook end-to-end path is Supabase-only and is NOT exercised by the SQLite CI suite.** The refactor (`_process_reply` extraction + buffer dispatch + recovery) is import-checked and the pure/orchestration cores are unit-tested, but the full live path (aggregation → Claude → send) needs a **manual smoke test** from the two approved numbers before relying on it. Rollback is one env var: `WHATSAPP_MESSAGE_AGGREGATION_ENABLED=false`.
- In-process debounce timers assume a **single uvicorn worker**; multi-worker safety comes from the DB claim (`claim_for_processing`) which prevents double-processing but not duplicate timers. Document/keep single-worker for now.
- Pricing-specific structured logs (e.g. `order_discount_applied`) from spec §28 were not added on the hot path to avoid noise; the discount is fully snapshotted on the order for audit. Turn-lifecycle logs ARE emitted.
- The three new SQL migrations must be applied to the dev/test Supabase project before the live path uses the new columns.

## 13. Security / privacy notes

- No secrets added. Phone numbers stay masked in logs. Location coords are stored in message metadata (backend) for turn reconstruction — not exposed to customers or facilities.

## 14. Commands to run

```bash
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest -q            # full backend suite
./.venv/Scripts/python.exe -m pytest tests/test_order_discount.py tests/test_message_aggregation.py tests/test_turn_service.py tests/test_final_pricing.py -q
# Apply migrations 000011–000013 to the dev/test Supabase project.
```

## 15. How to verify manually

Send (rapidly, from an approved number): `Hi` / `I need wash and fold` / `tomorrow` / `after 6 PM` / `from Dubai Marina` → expect ONE reply. Ask `How much is the 6 kg Wash & Fold bag?` → `AED 60`. Build a >AED 100 exact order → expect the 15% discount block, final price net of it, no VAT line.

## 16. Next recommended step

Manual WhatsApp smoke test of the aggregation + discount paths from the two approved numbers, then commit (owner commits to `main` on request).
