# Build Report — B2B Lead Entity (Agent Hardening Slice 4)

- **Date:** 2026-07-27
- **Objective:** Give B2B enquiries (hotel / restaurant / uniform / commercial / bulk / partnership) their own lead entity routed to the commercial team — never the consumer pickup funnel, never counted in consumer conversion metrics. Detection already existed; this adds the durable record + intake + acknowledgement.

## What was built
- **`services/b2b.py`** (pure) — `classify_business_type` (keyword → hotel / restaurant / uniform / commercial_laundry / bulk_outsourcing / facility_partnership / other) and `acknowledgement` (routes to the commercial team + asks for company / services / volume; **never** quotes a price or terms).
- **`db/repositories/b2b_leads_repo.py`** — `create` (generates `B2B-XXXXXXXX`, validates business_type → other), `get_open_for_conversation` (idempotency), `update_details` (whitelisted qualifying fields), `get`, `list_open`.
- **Migration `20260727_000025_b2b_leads.sql`** — `b2b_leads` table (company / contact / business_type / location / market / estimated_volume / required_services / frequency / current_provider / preferred_meeting_time / status / assigned_team, RLS + trigger + markers). Additive/idempotent.
- **Wiring (`api/evolution_webhooks.py`):** the escalation block now has a `b2b_lead` branch — creates a B2B lead (idempotent per conversation), opens an `AWAITING_OPERATIONS_RESPONSE` task for Sales, and sends one gated B2B acknowledgement. Complaint and B2B branches are mutually exclusive (`if complaint … elif b2b_lead …`).

## Why
Historical data showed ~23 B2B leads mixed into the consumer archive. Forcing a hotel/commercial enquiry through the bag-and-pickup consumer flow is wrong and pollutes conversion metrics. B2B now gets a clean, separately-tracked lead for the commercial team.

## Database / agent / API / UI
- **DB:** migration 000025 (1 table). **Agent:** B2B enquiries get a routed acknowledgement + a lead record + a Sales task (deterministic, no LLM). Slice-1 CRM already tags such customers `is_b2b` / lifecycle `b2b_lead`. **API/UI:** none this slice (ops dashboard read + Claude B2B intake tool are follow-ups).

## Mock-only / live
- Runs live against dev/test Supabase. No pricing/terms ever promised. No LLM calls. The B2B ack sends only when replies are allowed.

## Tests run + results
- **`tests/test_b2b.py` — 11 passed** (business-type classification across all types, ack routes-to-team + never quotes price/%/AED + asks for qualifiers, repo coerces unknown type, `update_details` column whitelist rejects an injected column).
- **Full backend suite — 685 passed** (674 → 685, +11), 157s. No regressions.
- **Live Supabase smoke:** applied 000025, created a `hotel` lead (`B2B-3BCA741A`, team "Sales / Partner Acquisition"), patched company/volume via `update_details`, cleaned up. Ref generation, whitelist patch, FKs validated end-to-end.

## Known limitations
- Conversational B2B intake (collect company/volume/services over multiple turns) is not built — the lead is created from the triggering message + `update_details` is available for ops/tools to fill later.
- Exclusion of B2B from consumer conversion metrics is enforced by keeping B2B in its own entity; the actual metrics rollup that must skip them arrives in Slice 5.
- No Claude-facing B2B intake tool yet (detection short-circuits before the LLM).

## Security / privacy notes
- `location` stores an area/city label only (no full private address required). No pricing exposure. Lead is routed to the commercial team; consumer PII rules unchanged.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_b2b.py -q`
- Apply migration (dev/test): execute `supabase/migrations/20260727_000025_b2b_leads.sql`.

## Next recommended step
Slice 5 — quality-metrics reporting: deterministic rollups (price-enquiry→booking, booking→confirmed, repeat rate, escalation rate, conversion by service/country/segment) over orders/flags/turns, **excluding B2B leads** from consumer conversion, with a read API for the ops dashboard.
