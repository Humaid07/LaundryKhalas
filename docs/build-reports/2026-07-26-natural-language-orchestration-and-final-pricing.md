# Build Report — Fix stopped responses, natural conversation, grounding & final customer pricing

**Date:** 2026-07-26
**Author:** Engineering (Claude Code session)
**Status:** ✅ Backend implemented + tested (489 passing). Frontend/admin sweep delegated (see §10). Live WhatsApp acceptance pending (manual, from the two approved numbers).

---

## 1. Build title
Repair the WhatsApp agent after the Anthropic integration: stop the silent no-reply failure, replace scripted numbered-menu (IVR) behaviour with natural language, keep every business fact grounded in the backend, and make every customer-facing price a FINAL price (5% already included) with no VAT wording anywhere.

## 2. Date
2026-07-26.

## 3. Task objective
1. Customers can message naturally and always get a reply (never silence).
2. No numbered-menu requirement; free text is understood, multiple details extracted from one message, already-collected fields never re-asked.
3. All services/prices/turnaround come from the deterministic engines via validated tools — the model never invents business data.
4. Customer-facing prices already include the 5% adjustment; no "VAT/tax/excl/incl/subtotal" wording appears on any customer surface; the 5% is applied exactly once.

## 4. What was built (root causes → fixes)

### 4.1 Root cause of "stopped responding"
The LLM tool-loop can legitimately produce an **empty final text** (Claude ends a turn on a tool call, a truncation, or the tool-round limit → mock fallback). The webhook then sent that empty string to Evolution, which is a silent no-op/400 — the customer saw nothing. The pre-LLM deterministic FSM never produced empty text, which is exactly why it regressed after the integration.

**Fix — three empty-reply guards (spec §2, §29):**
- `api/evolution_webhooks._send_reply` substitutes a professional fallback (`_AI_FALLBACK_TEXT`) if the reply text is blank — no path can send an empty WhatsApp message.
- `booking_tools.run_booking_turn` guarantees a non-empty return: on blank model text it substitutes `next_step_prompt(row)` — a deterministic, **grounded** next question derived from the live workflow state (asks only for what's missing).
- The non-booking send path guards `agent_reply.text` the same way.
- On an AI-turn exception the webhook sends the fallback **and** escalates the conversation to a human (flag + ticket + `human_needed`), so failure is visible, never silent, and never a false confirmation.

### 4.2 Natural conversation (remove IVR)
- `settings.anthropic_booking_orchestration` default flipped **False → True** (owner decision). Claude now orchestrates the conversation whenever a live provider is configured; the deterministic FSM remains the offline/fallback path.
- Rewrote `booking_system_prompt()` from "collect ONE detail at a time / call each tool at most once" (IVR-shaped) to: understand the whole message, **extract and save every detail at once**, then ask only for what's still missing — one friendly question, never a checklist, never a numbered menu.
- **Lazy order creation:** the draft order is created only on the first booking **write** tool (`_ensure_draft`). A pure question ("how much is sneaker cleaning?", "hi") is answered via read-only tools and creates **no** order.
- The webhook now passes recent conversation **history** into the turn (so "the smaller bag" resolves in context), and wires **real escalation** when the model calls `request_human_support` (the tool only signals intent; the backend owns flags/tickets/human status).

### 4.3 Grounding (unchanged principle, widened)
- The one orchestration assistant now has both the **write** tools (save_*/confirm_order) and the read-only **grounding** tools (`lookup_item_price`, `estimate_turnaround`, `check_service_area`) — 17 tools, no duplicate names. Every price/turnaround/area/slot/service is read from the deterministic engines; the prompt forbids stating any figure not returned by a tool.
- `confirm_order` stays guarded (rejects while any field is missing) and idempotent — the injection defence: even told "just confirm", the backend refuses.

### 4.4 Final customer pricing (5% included, zero VAT wording)
- New **`services/money.py`** — the single Decimal (HALF-UP, 2dp) money utility: `final_unit_price(base, vat_rate, prices_include_vat)`, `final_line_total` (per-unit rounded then × qty, spec §20), `vat_breakdown` (internal accounting only), `format_money`. The 5% is applied in exactly one place and never twice (spec §18: `prices_include_vat=True` returns the stored price unchanged).
- Refactored **`services/pricing.py`**: `QuoteLine.unit_price`/`line_total` are now the FINAL customer figures (with `base_unit_price`/`base_line_total` kept for internal accounting); `Quote.customer_total`; `format_quote_lines`/`format_quote_summary` show only the final price and **never** "VAT/tax/excl/incl/subtotal". Internal `subtotal_excluding_vat`/`vat_amount` are derived back from the final total so accounting still reconciles (spec §24).
- Converted every other customer-facing surface: `catalogue.item_price_label`, webhook `_final_confirmation_text` ("Price: AED 63"), booking-tools state block (`final_price_aed`) + summary, `llm_tools` price guidance, `price_resolver._public_projection` + `public_pricing._json_fallback` (final prices; `price_note` replaces `vat_note`), `orders_repo._pricing_block` (added `final_price`).
- Worked examples now produced by the engine: 60→63, 80→84, 7→7.35, 9→9.45, 11→11.55, 50→52.50; 3 shirts → AED 28.35; 3 shirts + 2 trousers → AED 51.45.

## 5. Files created
- `apps/whatsapp-agent/services/money.py`
- `apps/whatsapp-agent/tests/test_final_pricing.py` (14 tests)
- `apps/whatsapp-agent/tests/test_orchestration_delivery.py` (10 tests)
- `apps/whatsapp-agent/tests/test_webhook_delivery.py` (3 tests)
- `docs/build-reports/2026-07-26-natural-language-orchestration-and-final-pricing.md` (this report)

## 6. Files modified
- `services/pricing.py` — final-price QuoteLine/Quote, Decimal totals, VAT-free wording.
- `services/catalogue.py` — `item_price_label` returns final price.
- `services/price_resolver.py` — `_public_projection` final prices + `price_note` (dropped `_vat_note`).
- `api/public_pricing.py` — `_json_fallback` final prices + `price_note`.
- `api/evolution_webhooks.py` — orchestration is the default path, history passed, escalation wired, empty-reply guards, `_final_confirmation_text` final/VAT-free, structured logging.
- `agents/whatsapp_agent/booking_tools.py` — rewritten natural-language prompt, lazy draft, grounding tools added, `next_step_prompt` empty-reply guard, VAT-free state block.
- `agents/whatsapp_agent/llm_tools.py` — price-tool guidance now says the label is the final price, never mention VAT.
- `db/repositories/orders_repo.py` — `_pricing_block` exposes `final_price`.
- `settings.py` — `anthropic_booking_orchestration` default True.
- Updated 9 pre-existing tests in `tests/test_pricing_management.py`, `tests/test_catalogue_pricing.py`, `tests/test_item_booking_flow.py` to the final-price contract.

## 7. API endpoints added/changed
No routes added/removed. Behaviour changes: `POST /webhooks/evolution` now runs the natural-language orchestration path by default; `GET /api/public/pricing*` returns FINAL prices and `price_note` instead of base prices + `vat_note`; order-detail responses include `pricing.final_price`.

## 8. Database
No schema/migration change. Order snapshots now store FINAL line figures (`unit_price`/`line_total`) plus internal `base_*`; accounting columns (`subtotal_amount`/`vat_amount`) unchanged. Historical order snapshots are immutable and are NOT re-priced (verified by test).

## 9. Agent behaviour added/changed
Natural-language, multi-field extraction; unified Q&A + booking; lazy order creation; grounded figures; guaranteed non-empty replies; model-initiated human handoff wired to real flags/tickets.

## 10. UI / frontend (done — `apps/admin` tsc 0 errors)
All customer-facing VAT/tax wording was concentrated in the order-detail pricing UI and was removed; price displays now use the final amount:
- `order-detail/OrderItemsTable.tsx` — dropped "Subtotal (excl. VAT)" / "VAT (5%)" / "(incl. VAT)" rows → single "Total"/"Estimated total" from `pricing.final_price`; line figures via `formatMoney`.
- `order-detail/cards.tsx` (`PaymentSnapshotCard`) — removed subtotal/VAT fields; total reads `final_price`.
- `order-detail/OrderSummaryStrip.tsx` — reads `pricing.final_price` (was the internal `estimated_total_including_vat`).
- `pricing/PricingManagement.tsx` — admin edits the **base/original** price and sees a read-only **"Customer-facing price (final)"** preview (`base × 1.05`, half-up 2dp); WhatsApp/Website publish previews render the final price; "Prices exclude 5% VAT." → "Final price."
- `lib/dashboard/formatters.ts` — new `formatMoney` (clean whole numbers, 2dp otherwise, decimal-safe).
- `lib/dashboard/whatsapp-agent-api.ts` — `final_price` added; VAT fields typed as INTERNAL-only; line `unit_price`/`line_total` documented as final (+ optional internal `base_*`).

Env/mode chips ("Live Stripe: Off", etc.) left as-is. There is **no real Stripe integration** — it is a mock/off status label only, so no charge logic needed changing. Verified with `npm run typecheck` (`tsc --noEmit`) → **exit 0, 0 errors**. `next build` intentionally not run (known Windows 500.html failure).

## 11. What is mock-only / live
- Offline/tests: `LLM_PROVIDER=mock` → deterministic FSM + mock replies (byte-identical to before; hermetic suite).
- Live: with `LLM_PROVIDER=anthropic` + key + `WHATSAPP_MODE=evolution` + allow-list + `WHATSAPP_AGENT_MODE=test`, the orchestration path calls the real API and replies to the two approved numbers only.

## 12. What is intentionally deferred
- Live-API smoke this session (rotate the previously-exposed key first).
- Per-conversation locking / `workflow_version` for truly concurrent messages.
- A dedicated `llm_usage_events` table (usage still persisted to `messages.metadata`).
- Splitting a mixed eligible/ineligible order across two delivery SLAs (still declines whole-order Express).

## 13-18. Tests
- **Baseline before:** 459 passed. **After:** **489 passed**, 0 failures (~133s), suite hermetic (`conftest` forces mock).
- New coverage: Decimal final-price values (60→63, 80→84, 7→7.35, 9→9.45, 11→11.55), per-unit-rounded line totals, no-double-application, no-VAT-wording in summaries/labels/public API, lazy order creation (question ≠ order), first-write-creates-draft, guarded confirm, empty-model-text → grounded next step, model-requested human support, confirmation text final/VAT-free, `_send_reply` never sends empty.
- **Bug found & fixed:** empty LLM final text was delivered as an empty WhatsApp message (the "stopped responding" root cause).

## 19. Known limitations
- Natural-language quality depends on the live model; the deterministic `next_step_prompt` guarantees forward progress but is terser than the model.
- Combined orders with both Express-eligible and ineligible services decline whole-order Express (no split delivery yet).

## 20. Security / privacy
- No key echoed/logged; API key stays in the gitignored `.env`. Logs use masked phone numbers and safe identifiers only.
- Grounding tools read catalogue/SLA/area config only — no customer PII in tool inputs. Workflow state block hides internal UUIDs (test-verified).

## 21. Cost / LLM usage
Orchestration means ~1 Claude turn (often with 1–3 tool round-trips) per inbound message. Prompt-caching keeps the stable system prompt + tools cheap on repeat turns. Per-turn tokens/cost are logged. For high volume, set `LLM_MODEL=claude-haiku-4-5` (operator choice).

## 22. Screens/pages to demo
WhatsApp conversation from an approved number (natural booking + a price question) and the dashboard order detail showing a single final price.

## 23. Commands to run
```bash
cd "D:/Laundry Khalas App/apps/whatsapp-agent"
DATABASE_MODE=sqlite ./.venv/Scripts/python.exe -m pytest -q     # 489 passed
```

## 24. How to verify manually (approved numbers only — do NOT simulate)
With live env set, message from +971543216640 / +971502485658:
- "Hi, I need laundry pickup." → natural question, no menu.
- "I have three shirts and two trousers for wash and press." → both items + quantities stored, asks only the next missing detail.
- "How much is the 6 kg Wash & Fold bag?" → "AED 63" (no VAT wording).
- "How much is sports sneaker cleaning?" → "starts from AED 52.50 per pair …".
- After summary: "Change my pickup time to 8 PM." → only the time changes.
- "Can you return my shoes in 12 hours?" → declines Express, ~2–3 days.

## 25. Next recommended step
1. Rotate the exposed Anthropic key, then run one live-API smoke of the orchestration turn.
2. Manual WhatsApp acceptance from the two approved numbers.
3. Merge the frontend sweep once its tsc passes.
4. Commit (owner rule: commit directly to `main` when asked).
