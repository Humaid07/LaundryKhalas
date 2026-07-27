# Build Report — Structured Complaints + Durable Pending Tasks (Agent Hardening Slice 2)

- **Date:** 2026-07-27
- **Objective:** Replace generic complaint handling with a **structured complaint record** (category / item / photo ref / requested resolution / urgency) and make every "I'll get back to you" promise a **durable pending operational task** (the 7 `AWAITING_*` types) with due time, follow-up and escalation. Add an empathetic complaint acknowledgement that never promises compensation.

## What was built
- **`services/complaints.py`** (pure) — `classify_category` (keyword refinement → coarse escalation-category fallback → `other`), `detect_requested_resolution`, `urgency_from_priority`, and `empathetic_ack` (apologises, asks ONLY for the missing detail — order ref / photo — and **never** promises refund/replacement/compensation, CLAUDE.md §6).
- **`services/pending_tasks.py`** (pure) — `TASK_TYPES` vocabulary + per-type SLA (`due_hours`/`follow_up_hours`/`escalation_team`) from `config/pending_tasks.json`.
- **`db/repositories/complaints_repo.py`** — `create` (generates `CMP-XXXXXXXX`, validates category → `other`), `get`, `list_open`, `set_status`.
- **`db/repositories/pending_tasks_repo.py`** — `create` (generates `TSK-XXXXXXXX`, computes `due_at`/`follow_up_at` DB-side via `now() + interval` from the type SLA, rejects unknown types), `list_open`, `list_overdue` (escalation sweep), `mark_done`, `mark_escalated`.
- **Migration `20260727_000024_complaints_pending_tasks.sql`** — `complaints` + `pending_tasks` tables (RLS-enabled, `set_updated_at` triggers, standard markers). *Renumbered from 000023 to avoid a collision with a concurrent session's `000023_facility_drivers.sql`; the table sets are disjoint.*
- **Wiring (`api/evolution_webhooks.py`):** in the escalation block, for **complaint-type flags** (`refund_request`, `payment_issue`, `damaged_item`, `missing_item`, `complaint`, `late_delivery`) it now creates a structured complaint + an `AWAITING_COMPLAINT_REVIEW` pending task, and sends **one** deterministic empathetic acknowledgement — gated by `live and mode != paused and status != human_takeover` so it never talks over a human or replies when paused. B2B/handoff flags are unchanged (B2B lead entity is Slice 4). All complaint/task/ack steps are best-effort and never break the escalation handoff.

## Why
Historical chats showed frequent complaints and many "let me check with the facility / Operations" promises that vanished into the chat with no tracking. Escalation previously created only a generic ticket and sent the customer **nothing**. Now complaints are typed + queued for Operations, promises are durable and follow-up-able, and the customer gets an immediate, safe, empathetic acknowledgement.

## Database / agent / API / UI
- **DB:** migration 000024 (2 tables). **Agent:** the escalation path now sends an empathetic ack + creates structured records (deterministic, no LLM). **API/UI:** none this slice (ops-dashboard reads + Claude `create_complaint`/`create_pending_task` tools come in Slice 3).

## Mock-only / live
- Runs live against dev/test Supabase. The empathetic ack sends via Evolution only when replies are actually allowed. No compensation is ever promised or paid. No LLM calls.

## Tests run + results
- **`tests/test_complaints.py` (15) + `tests/test_pending_tasks.py` (11) — 26 passed** (category classification incl. keyword + escalation fallback, resolution detection, urgency mapping, ack asks-only-missing + never-promises-compensation across all categories, SLA config coverage, repo type/category guards).
- **Full backend suite — 666 passed** (626 → 666, +40), 185s. No regressions from the webhook wiring.
- **Live Supabase smoke:** applied 000024, created a `damage`/high complaint (`CMP-0E7B2718`) + an `AWAITING_COMPLAINT_REVIEW` task (`TSK-884A548C`, due +4h / follow-up +2h computed DB-side), `list_open` returned it, then cleaned up. Validated ref generation, interval SLA, FKs end-to-end.

## Known limitations
- Photo presence isn't detected yet (Evolution discards image bytes; bespoke media deferred), so the ack always offers "a photo" for visual categories and `photo_ref` stays null.
- Complaint intake is single-shot (created from the triggering message); a multi-turn intake FSM (collect item/description conversationally) is a follow-up.
- No overdue-task **sweeper job** wired yet (`list_overdue` exists; a scheduled escalation runner is a later slice).
- Claude-facing `create_complaint` / `create_pending_task` tools deferred to Slice 3.

## Security / privacy notes
- The ack carries no PII and no promises. Complaint/task rows store operational data only; the empathetic message is deterministic (no model text). Complaint join/creation scoped by the conversation's `customer_id`.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_complaints.py tests/test_pending_tasks.py -q`
- Apply migration (dev/test): execute `supabase/migrations/20260727_000024_complaints_pending_tasks.sql`.

## Next recommended step
Slice 3 — add the missing Claude tools (pickup slots, customer record, saved addresses, delivery info, start-another-order) **plus** the `create_complaint` / `create_pending_task` tools now that their backends exist; prompt hardening (facility cost/margin/other-customer); `shortening` alias; empty-text guard on the grounded path.
