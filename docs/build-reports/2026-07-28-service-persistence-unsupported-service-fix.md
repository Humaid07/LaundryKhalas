# Build Report — Service Persistence & Unsupported-Service Handling (WhatsApp Booking)

**Date:** 2026-07-28
**Area:** WhatsApp Operations Agent — Claude-orchestrated booking (`apps/whatsapp-agent`)

## 1. Objective
Make the WhatsApp booking agent behave like a natural, context-aware CSR: never
lose the selected service while moving through pickup scheduling, never re-ask a
question already answered, correctly recognise unsupported (non-laundry)
requests such as "haircut", and never send a duplicate reply for one logical
customer turn.

## 2. Reproduced failure (from the screenshot)
Customer selected a service → went through pickup date + time → agent asked
**"Which service do you need today?"** again → customer replied **"haircut"** →
agent asked the same service question again; the same message appeared twice.

## 3. Root causes (traced through the real code path)
The production path is **Claude orchestration** (`anthropic_booking_orchestration=True`),
which drives booking through controlled write-tools in
`agents/whatsapp_agent/booking_tools.py`. The DB (`orders`) is already the source
of truth, `get_active_draft` reloads fresh each turn, and `apply_booking_updates`
is a column-whitelisted PATCH — so service persistence across pickup steps was
structurally sound. The actual defects were:

1. **Unsupported vs. unrecognised were conflated.** `save_service_selection`
   called `bf.resolve_service`, which returns only `ok | ambiguous | invalid`.
   Both a typo AND a non-laundry request ("haircut") returned `invalid`, and the
   tool responded with a **tool error** — *"That service isn't in the catalogue.
   Show list_service_categories and ask."* That error nudged Claude to **re-ask
   which service**, even when a valid service was already stored. This is the
   repeated-service-question root cause.
2. **No "already selected / preserve existing" guard.** Nothing stopped a second
   `save_service_selection` call (with a bad value) from prompting a re-ask; the
   tool didn't consult whether a valid service was already saved.
3. **No bespoke path** — a specialty request ("heavily embroidered wedding
   dress") would either alias to a normal category or error.
4. **No outbound idempotency key.** Inbound dedup (`wa_message_seen`) and
   single-turn processing (`turns_repo.claim_for_processing`) existed, but a
   delivered reply had no idempotency key, so a restart re-drive / retry of a
   turn that sent-then-crashed could resend.

(If the failing session was running the deterministic **MockProvider** with live
LLM off, its scripted *"Which service do you need today?"* is the exact string in
the screenshot — the fix targets the real Claude path the spec is about; the mock
is a rule-based fallback with a known accuracy ceiling.)

## 4. What was built
- **`services/service_resolution.py` (new)** — authoritative, deterministic,
  offline classifier `classify_service_request()` → `ServiceKind` of
  `EXACT | ALIAS | AMBIGUOUS | BESPOKE | UNSUPPORTED | NONE`. Reuses the SAME
  `booking_flow.resolve_service` catalogue resolver (no drift), adds a narrow
  bespoke-signal set (checked first so "embroidered wedding dress" → bespoke) and
  a whole-word non-laundry term set (checked only after catalogue resolution
  fails, so nothing the catalogue knows is ever mislabelled). `supported_categories()`
  reads the live catalogue for the "what we DO offer" line.
- **`agents/whatsapp_agent/booking_tools.py`** — `save_service_selection`
  rewritten to classify first:
  - `UNSUPPORTED` → returns a **non-error** result (`unsupported_request:true`)
    that **preserves an in-progress booking**, sets `next_missing_field`, lists
    supported categories, and instructs the model to politely decline and
    continue — **never** re-ask which service, never invent a price/route.
  - `BESPOKE` → routes to the photo + location flow (`AWAITING_CUSTOMER_PHOTO`),
    no invented price.
  - `AMBIGUOUS` → one clarification.
  - same service already saved → **no-op** (`already_selected:true`).
  - unrecognised **with** a service already saved → preserve it, don't re-ask.
  - The tool was removed from `_WRITE_TOOLS` so an unsupported request **creates
    no draft order** (a draft is created only when a supported service is saved).
- **System prompt hardened** (`booking_system_prompt`) with an authoritative-state
  block: ask only fields in `missing_fields`; a saved service is never in
  `missing_fields`, so never ask which service when one is selected; keep a saved
  service through scheduling/pricing/unrelated messages; handle `supported:false`
  by declining + continuing; handle `bespoke:true` via photo/quote.
- **Outbound idempotency** — `messages_repo.agent_reply_key_seen()` (new) +
  `_reply_idem_key()` + a check in `_deliver` (`api/evolution_webhooks.py`).
  Key = `sha1(turn_id | workflow_state | reply body)`, stored in the agent
  message metadata; a reply whose key was already delivered is skipped and logged
  `duplicate_outbound_prevented`. `turn_id` is threaded from the aggregation and
  restart-recovery processors.
- **Structured logs** (safe ids only — conversation, order number, response_type,
  kind, no PII): `service_candidate_detected`, `service_selection_persisted`,
  `service_already_selected`, `existing_service_preserved`, `service_edit_requested`,
  `unsupported_service_detected`, `bespoke_service_detected`,
  `duplicate_outbound_prevented`.

## 5. Files
**Created:** `services/service_resolution.py`,
`tests/test_service_resolution.py`, `tests/test_service_persistence.py`,
`tests/test_outbound_idempotency.py`, this report.
**Modified:** `agents/whatsapp_agent/booking_tools.py`,
`db/repositories/messages_repo.py`, `api/evolution_webhooks.py`.

## 6. API / DB / UI
No API routes changed. **No DB migration** (uses existing columns + the existing
`messages.metadata` jsonb for the idempotency key — deliberately avoided a
migration due to concurrent migration-number contention). No UI changes.

## 7. Mock vs live
All new logic is deterministic backend logic (mock-first). No live WhatsApp /
LLM / Stripe calls added. The idempotency guard is DB-backed (Supabase).

## 8. Tests run & results
`ruff check` — clean on all changed files.
- `tests/test_service_resolution.py` — 9 passed
- `tests/test_service_persistence.py` — 11 passed
- `tests/test_outbound_idempotency.py` — 5 passed
- Regression subset (booking tools/flow, webhook delivery, turns, aggregation,
  discount, multi-order, evolution channel, item booking) — **190 passed**, 0
  regressions.
- Known pre-existing flake: the shared-SQLite demo-order reseed fixture
  (`LK-AE-1024..1027`) can raise a UNIQUE-constraint error depending on test
  order; passes on isolated rerun; unrelated to these changes (the new tests use
  an in-memory fake repo).

### Scenario coverage (maps to the spec's required tests)
saved service survives pickup date+time · survives an invalid date · haircut
during an active booking preserves the booking + returns to pickup-address ·
haircut with no order creates no order · bespoke wedding dress → bespoke flow ·
ambiguous "ironing" → clarification · adding an item preserves the service ·
service edit updates only the service · empty/null service can't erase a saved
one · same service is a no-op (no re-ask) · idempotency key stable per turn /
distinct across turns / distinct replies in a turn.

## 9. Known limitations / deferred
- A service **edit** relabels the category but does **not** wipe existing item
  lines (a deliberate safety choice so an *additional*-service item, which Claude
  also routes through `save_service_selection`, is never lost); items re-collect
  for the new category. Full edit-time reprice is deferred.
- End-to-end backend-restart and two-number isolation are covered structurally by
  the existing durable turn model + fresh per-turn draft reload; they are not
  re-proven here with a live-DB integration test.
- The deterministic MockProvider fallback remains rule-based (unchanged).

## 10. Security / privacy
Logs carry only safe ids (conversation id, order number, response_type, service
kind) — no phone, address, or secrets. Unsupported/bespoke handling never invents
a price or a service and never routes a non-laundry request to a facility.

## 11. How to verify manually
With live Evolution + live LLM, from an approved test number: pick a service →
give pickup day + time → the agent asks only for the address (never the service
again). Send "haircut" mid-booking → it politely declines, keeps the booking, and
asks for the address. Send "haircut" with no booking → it declines and lists what
we offer, creating no order.

## 12. Next recommended step
Wire an edit-time reprice for a genuine category change, and add a live-DB
integration test for restart recovery + two-number isolation.
