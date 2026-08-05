# Build Report — WhatsApp Agent Production Update, Phase 2c (Follow-up Scheduler core)

**Date:** 2026-08-05
**Status:** Centralized follow-up **policy engine** implemented + tested; persistence table +
sweeper + call-site wiring deferred (see §5). Verification run in progress (appended below).
UNCOMMITTED.

## 1. Objective
Sections 14 / 24 / 25 — one centralized follow-up scheduler so a customer never gets
overlapping price / payment / website-abandonment / pickup nudges, follow-ups respect the
10 PM local cutoff, and each is idempotent. This increment delivers the pure, deterministic
policy core (timing, cutoff, suppression, "only the most relevant" arbitration, templates).

## 2. What was built
- **`config/followups.json`** — single source of truth: per-type offset minutes (payment 6 /
  15, quote 6, web 10 / 40 / 400, pickup 0), the messaging window (`start_hour` 8,
  `cutoff_hour` 22 = the 10 PM cutoff), and the priority order.
- **`services/followups.py`** (pure, no I/O):
  - Type constants: `PAYMENT_STRIPE`, `PAYMENT_CASH`, `QUOTE_INACTIVITY`,
    `WEB_ABANDONMENT_1/2/3`, `PICKUP_REMINDER`.
  - `compute_due_at(anchor, type)` = anchor + offset, then `shift_into_window()` — the 10 PM
    cutoff: due at/after 22:00 → next day 08:00; before 08:00 → same day 08:00; else unchanged
    (market-local via `services/clock`).
  - `SuppressionContext` + `is_suppressed(type, ctx)` — universal suppressors (customer
    replied, human takeover, opted out, already sent, order cancelled, provider policy) plus
    per-family rules (payment: paid / cash already chosen; web: no consent / invalid number /
    converted / already ordered; quote: already ordered).
  - `select_next(candidates, ctx_by_type, now)` — the §25 arbitration: among follow-ups that
    are due, in-window and un-suppressed, the highest priority wins (ties → earlier due). So
    overlapping nudges never all fire — only one is sent.
  - Approved templates (§§14, 24, 26) + `render(type, persona)` (fills the persisted persona;
    all pass the reply-style validator — no emoji / exclamation / dash). The 25% abandonment
    figure is the only approved offer and is applied via the discount engine on reply, never a
    promised final total.
  - `dedupe_key()` for idempotency.

## 3. Files
**Created:** `config/followups.json`, `services/followups.py`, `tests/test_followups.py`.
**Modified:** none.
**Migrations:** none this increment (persistence table deferred — next free number is `000042`,
since another session's live-Stripe work took `000041`).

## 4. Tests
- `tests/test_followups.py` — 21 tests: config-driven offsets/priority, `compute_due_at`, the
  10 PM cutoff (after-cutoff → next morning; before-window → window start; within → unchanged),
  every universal + per-family suppressor, arbitration (highest-priority-due wins /
  skips-suppressed / none-outside-window / none-when-not-due), dedupe-key stability, template
  render + style safety. **Green.**
- Full-suite regression (excluding the 3 classifier files and the 3 in-flight Stripe files —
  both other sessions' work): result appended.

## 5. Phase 2c-part-2 — persistence + sweeper orchestration (added)
- **`scheduled_followups`** durable queue — migration `000042`
  (`20260805_000042_scheduled_followups.sql`, checked `status`, unique `dedupe_key`, due/conv
  indexes, RLS deny-all) + matching `models.py` `ScheduledFollowup` ORM model (SQLite).
- **`services/followup_scheduler.py`** (pure):
  - Scheduling builders — `payment_silence_rows` (§14: Stripe +6 min, cash +15 min),
    `web_abandonment_rows` (§24: +10 / +40 / +400 min), `quote_inactivity_row` (§25: +6 min),
    each producing ready-to-persist rows with policy-computed `due_at` + a `dedupe_key`.
  - Sweeping — `plan_conversation` (one send via `followups.select_next`) and `plan_batch`
    (at most ONE send per conversation across the whole due set — §25).
- **`tests/test_followup_scheduler.py`** — builders' due-times/dedupe + one-send-per-conversation
  + per-conversation suppression.

## 6. Phase 2c-part-3 — repo + sweeper + call sites (added)
- **`db/repositories/scheduled_followups_repo.py`** — idempotent CRUD: `schedule`
  (ON CONFLICT dedupe_key DO NOTHING), `load_due`, `mark_sent`, `mark_suppressed`,
  `cancel_for_conversation`.
- **`scripts/run_due_followups.py`** — the cron sweeper (mirrors `scripts/expire_drafts.py`):
  loads due rows, builds the LIVE suppression context per row from the DB (customer replied
  since anchor / human takeover / paid / cash chosen / order confirmed), lets the policy pick
  one send per conversation, and sends through the SAME safety gates as the webhook — never
  when paused; in test mode only to the allow-list. Marks rows SENT / SUPPRESSED. Supabase-only.
- **Call sites** (both Supabase-only, idempotent, never break the turn):
  - Payment silence (§14) — `set_payment_preference` arms the two payment follow-ups while the
    method stays UNDECIDED (`payment_preference.wants_payment_followups`).
  - Quote inactivity (§25) — `get_order_summary` arms one follow-up once an EXACT eligible
    quote is shown (not inspection/pending).

## 7. Phase 2c-part-4 — website Order-Now abandonment (§24) (added)
- **`services/web_order_intent.py`** (pure) — `evaluate_intent`: schedule outreach ONLY for a
  valid E.164 number + explicit consent; else record anonymously. **No fingerprinting**; an
  unsent prefilled WhatsApp message is never an inbound conversation.
- **`web_order_intents`** table — migration `000043` (RLS deny-all) + `models.py` `WebOrderIntent`.
- **`POST /api/web/order-intent`** (`api/web_intents.py`, public/unauthenticated, registered in
  `main.py`) — records every click via the ORM (works in SQLite + Supabase) and, for a consented
  visitor, arms the three abandonment follow-ups (Supabase-only, dedupe scoped to the web
  session; deterministic persona via `persona_assignment.select_for_key`).
- **`web_abandonment_rows`** now keys dedupe on the web session (`dedupe_scope`) with
  `conversation_id=None` (no conversation exists yet).
- **`tests/test_web_order_intent.py`** — pure gating, builder scoping, and the endpoint
  (anonymous → no outreach; consented → outreach flag; number-without-consent → none).

## 8. Phase 2c-part-5 — cancel-on-reply (added)
- **`api/evolution_webhooks._process_reply`** — on any inbound customer turn, proactively
  `scheduled_followups_repo.cancel_for_conversation(convo_id, "customer_replied")`
  (Supabase-only, best-effort, never breaks the turn). Completes the lifecycle: schedule on
  silence → cancel the moment the customer engages. The sweeper still re-checks
  `customer_replied` at send time, so this is a proactive cleanup, not the only guard.

## 9. Phase 2c-part-6 — pickup reminders + web-intent conversion (added)
- **Pickup reminder** — `followup_scheduler.pickup_reminder_row` (slot-relative: due N hours
  before the pickup window, shifted into the messaging window) + call site in `confirm_order`
  (`_schedule_pickup_reminder`, Supabase-only, future-pickup only, never breaks the turn).
- **Web-intent conversion** — `db/repositories/web_order_intents_repo.py`
  (`mark_converted_by_number`, `is_converted_number`); the webhook marks a visitor's intent
  converted when they first message on WhatsApp; the sweeper's suppression context now sets
  `converted` for WEB_ABANDONMENT rows via `is_converted_number`, so abandonment follow-ups stop
  once the visitor engages.
- Tests: `pickup_reminder_row` slot-relative + before-window-shift.

## 10. Follow-up scheduler — status
The centralized follow-up scheduler is **functionally complete** end-to-end: policy engine →
durable queue → scheduling at the payment / quote / website-abandonment call sites → cancel on
reply → cron sweeper that sends the single most-relevant follow-up per conversation through the
webhook's safety gates. Live delivery is exercised only in Supabase mode (the queue lives
there); the pure policy, orchestration, decision, and endpoint layers are all unit-tested.

## 6. Security / privacy
- Pure policy, no I/O, no secrets. Consent + opt-out are first-class suppressors; website
  outreach is gated on an explicit consented, valid number (§24).

## 7. Next
Wire persistence + the sweeper + the three call sites, and build the website order-intent
capture (§24) so the abandonment follow-ups become live.
