# Build Report — Campaign Attribution (Agent Hardening Slice 7, mock-first)

- **Date:** 2026-07-28
- **Objective:** Track outbound campaign context SEPARATELY from normal customer intent — a campaign table + per-recipient sends, last-touch attribution (7/14/30d), eligibility validation, a `campaign_responder` CRM feed, and a `get_campaign_eligibility` tool so the agent never grants an expired/ineligible offer. Mock-first (no live marketing source).

## What was built
- **`services/campaign.py`** (pure) — `load_campaigns` (from `config/campaigns.json`), `is_eligible` (active + within valid_from/valid_to + market match), `eligible_campaigns`, `find_by_code`, `pick_last_touch` (most recent send before the booking within the window).
- **`config/campaigns.json`** — 3 mock campaigns (new-customer 25% AE, winback 20% AE, an expired test campaign).
- **`db/repositories/campaigns_repo.py`** — `sync_from_config` (idempotent upsert), `record_send`, `attribute_booking` (last-touch SQL: credits the confirmed order to the most recent in-window send, marks it converted, idempotent per send), `has_converted_send`, `get_by_code`.
- **Migration `20260728_000026_campaigns.sql`** — `campaigns` + `campaign_sends` tables (RLS + triggers + markers).
- **`get_campaign_eligibility` tool** (booking_tools) — lists active offers or validates a specific `offer_code` for the customer's market/today; the model is instructed to apply ONLY what it returns as eligible, never an expired offer.
- **Wiring:** booking confirm now calls `campaigns_repo.attribute_booking` (best-effort); `crm_repo.gather_facts` reads `has_converted_send` → feeds the `campaign_responder` segment (Slice 1).

## Why
Historical data had ~307 campaign recipients with ~31 converting within 30 days. Campaign replies ("I want the 25% offer") must be validated + attributed separately, not treated as ordinary intent, and a customer converting after a returning/review campaign is a retention conversion — not new-customer acquisition.

## Database / agent / API / UI
- **DB:** migration 000026 (2 tables). **Agent:** new `get_campaign_eligibility` tool + prompt guidance; confirm-time attribution. **API/UI:** none this slice.

## Mock-only / live
- Campaigns are mock (config-defined). Eligibility/attribution logic is real and live-validated. Applying a campaign discount to pricing is deferred until a real campaign source exists — the backend still validates + attributes. No LLM/external calls added.

## Tests run + results
- **`tests/test_campaign.py` — 9 passed** (eligibility in/out of window + market, expired excluded, before-valid-from, last-touch picks most-recent-in-window + ignores post-booking/out-of-window, tool lists active/rejects expired/unknown).
- **Affected suites (campaign + CRM + booking tools + tool-loop) — 52 passed** together; the new tool didn't disturb the tool-loop assertions.
- **Live Supabase smoke:** applied 000026, synced 3 campaigns, recorded a send, `attribute_booking` credited the order to `NEW25-AE` (last-touch), `has_converted_send` = True, cleaned up. Validated the CTE + interval attribution SQL end-to-end.
- **Bug caught + fixed:** `sync_from_config` passed `valid_from`/`valid_to` as ISO strings → `asyncpg DataError` (binds by inferred type before a `::date` cast); fixed by converting to `date` objects in Python.

## Known limitations
- No `campaign_sends` are seeded from a real source, so attribution is a no-op until sends exist (a seed/import job is a follow-up).
- Campaign discount is not yet applied to order pricing (validated + attributed only) — deferred to when real campaigns + business rules exist.
- Multi-touch / first-touch models not implemented (last-touch default per spec).

## Security / privacy notes
- Campaign eligibility is backend-validated; the agent cannot grant an expired/ineligible offer. No PII in campaign definitions. Attribution stores only order/customer references + timestamps.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_campaign.py -q`
- Sync campaigns (dev/test): `campaigns_repo.sync_from_config()` after applying migration 000026.

## Next recommended step
Slice 9 — facility rates/margin + geo (mock): `facility_rates` + `margin_rule` + `facility_services` tables, rate-aware routing (lowest valid rate, margin applied, cost/margin hidden), market/country + capacity gates; mock rates. (Final planned slice; HubSpot slice dropped at owner's request.)
