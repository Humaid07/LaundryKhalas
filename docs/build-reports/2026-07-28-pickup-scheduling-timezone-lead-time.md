# Build Report — Timezone-aware pickup scheduling (same-day intent, lead-time slot filtering)

**Date:** 2026-07-28
**Area:** `apps/whatsapp-agent` (booking / Claude orchestration / availability)

## 1. Objective
Fix the WhatsApp agent's pickup date/time understanding so that "pickup now"/same-day
requests resolve to **today** without re-asking the day, and only **valid future**
pickup windows are offered (no passed / lead-time-violating slots), with the **backend**
as the authoritative source of current date/time (market timezone), relative-date
resolution, and availability.

## 2. Reproduced root causes
- **Past slots shown:** `db/repositories/slots_repo.available_slots()` filtered by
  weekday/emirate/service/capacity but had **no time-of-day filter** — for `today` it
  returned every window regardless of the current hour. No caller passed "now".
- **Re-asks "what day":** no "now"/same-day intent existed anywhere.
  `booking_flow.parse_pickup_date()` returned `invalid` for "pickup now", so `pickup_date`
  was never persisted → `workflow_state_block.missing_fields` kept `pickup_date` → the model
  (and FSM) re-asked. "11:30" then failed `save_pickup_time` ("set date first") → re-asked.
- **No tz authority / lead time:** two ad-hoc `+04:00` constants, **no `ZoneInfo`**
  (`tzdata` wasn't installed), no lead-time setting, and the current datetime was **never
  injected** into Claude's context. `delivery_sla.json`'s `timezone` was unused.

## 3. What was built

### New modules
- **`services/clock.py`** — backend clock authority. `now(market)` / `today(market)` return
  timezone-**aware** datetimes via `ZoneInfo` (market map: AE→Asia/Dubai, QA→Asia/Qatar,
  default = `settings.business_timezone`), with a fixed-offset fallback if a zone key is
  missing. Test/dev freeze via `settings.mock_now_iso` or `set_mock_now()`. Never uses server
  UTC as local.
- **`services/pickup_availability.py`** — availability engine. Takes raw slots + a
  timezone-aware `now` and drops today's windows that have **passed** or start before
  `now + lead`; reports `earliest_bookable_at`, `same_day_cutoff_passed`, machine-readable
  slot ids/start/end, eligibility reasons, and `next_available_date` when the day is done.
  Defensive: a slot without times is passed through, never crashes.
- **`services/pickup_datetime.py`** — deterministic temporal resolver. Resolves now / asap /
  today / tonight / this evening / later today / tomorrow[ morning] / day after tomorrow /
  yesterday / named weekday / "in two hours" / "after an hour" / "after six" / "around 5" /
  "at 7 tonight" against the backend clock. Returns intent type, resolved date, preferred
  time/daypart/lower-bound, same-day/immediate flags, validity, `clarification_required`, and
  a reason code (`RESOLVED_TODAY/TOMORROW/RELATIVE_TIME`, `PAST_DATE_INVALID`,
  `PAST_TIME_INVALID`, `AMBIGUOUS_TIME`, …).

### Settings (`settings.py`)
`business_timezone="Asia/Dubai"`, `pickup_minimum_lead_time_minutes=60`,
`pickup_allow_active_slot_booking=False`, `mock_now_iso=""`. `tzdata` added to `pyproject.toml`.

### Booking FSM (`services/booking_flow.py`)
- `parse_pickup_date(inbound, today, *, now=None, market=None)` now routes natural relative
  phrases through the resolver (so "now"→today, "yesterday"→`past`) before the strict calendar
  parser. Backward compatible (existing selection/text/format handling unchanged).
- `resolve_slot()` also accepts an exact `slot_id` or (case-insensitive) label, matching the
  Claude tool's contract; still only ever matches an OFFERED slot.

### Claude tools + context (`agents/whatsapp_agent/booking_tools.py`)
- `BookingContext` gains `now` (tz-aware) + `market`; `local_now()` derives from `today` when
  absent (tests). Webhook passes `clock.now(market)` / `clock.today(market)`.
- **State block** now carries `timezone`, `current_local_datetime`, `current_local_date`,
  `minimum_lead_time_minutes` (injected in `run_booking_turn` and `get_current_workflow`).
- **`get_available_pickup_slots`** rewritten → returns the rich `Availability` payload
  (tz, current datetime, resolved date, same-day cutoff, earliest bookable, filtered
  `available_slots` with ids/start/end/eligibility, `next_available_date`). Only eligible
  windows are ever handed to the model.
- **`save_pickup_time`** validates the choice only against **currently eligible** windows
  (a passed/lead-violating slot can't be saved) and now persists `pickup_start_time` /
  `pickup_end_time` (absolute window bounds), returning "this is a WINDOW not an ETA".
- **`save_pickup_date`** passes the market clock; on "yesterday" returns a polite past-date
  error; reports `same_day`.
- **New tool `resolve_pickup_datetime_intent`** — exposes the resolver to the model.
- **System prompt** gained a Scheduling block: resolve relative words from the backend clock,
  treat "pickup now" as today + earliest window, never re-ask a resolved day, show only
  tool-returned windows, handle passed times politely, offer windows (not exact ETAs), reject
  past dates politely.

### Webhook (`api/evolution_webhooks.py`)
`_today()` now uses `clock.today()`; `BookingContext` built with market `now`/`today`/`market`.

## 4. Mock-only / live
No live integrations touched. Pure scheduling logic + prompt/tool context. `tzdata` is a pip
package (no network at runtime).

## 5. Persistence
Uses **existing** columns (`pickup_date`, `pickup_slot_id`, `pickup_slot`, `pickup_start_time`,
`pickup_end_time`). The Claude path now persists start/end (it previously didn't).
**Deferred (staged):** the richer provenance columns (`pickup_date_source`,
`same_day_requested`, `pickup_time_intent`, `pickup_timezone`, `pickup_time_source`,
`minimum_lead_time_snapshot`, `availability_checked_at`, `slot_capacity_version`,
`customer_preferred_time`, `driver_eta`, `actual_pickup_at`) — these need a new additive
migration + `_BOOKING_COLS` whitelist update; **not applied** here to avoid a schema change on
the drifted shared dev/test Supabase without sign-off. The provenance is currently derived
in-turn and surfaced to the model; behavior is fully correct without the columns.

## 6. Tests & results
- **New:** `tests/test_pickup_scheduling.py` — **31 tests**: clock/timezone (incl. UTC-server →
  Dubai, tz-aware), availability filtering (1:03 PM → only 5–8/8–10 PM, 9 AM lead-time,
  future-date keeps all, no-same-day → next date, active-slot flag), resolver (now / same-day
  phrases / tomorrow morning / after six / in two hours / yesterday / 11:30 past vs not-past /
  next weekday), FSM parser (now→today, yesterday→past), and tool integration (state-block
  clock, save "now"→today drops `pickup_date` from missing, slots exclude passed windows,
  save_pickup_time rejects passed + persists bounds, resolve flags yesterday, next-date offer).
- **Regression:** booking FSM/tools/items/multi-order/orchestration/service-selection/
  customer-name/delivery — **158 passed** together (+ the 31). One cross-suite SQLite demo-seed
  collision (`LK-AE-1024`) is a pre-existing test-isolation quirk — the file passes alone.
- **ruff:** clean on all changed files.
- **End-to-end simulation** of the reported convo at 1:03 PM: "now"→today, no day re-ask,
  windows = only 5–8/8–10 PM, "ready for 11 30"→"11:30 AM has already passed today."

## 7. Known limitations / deferred
- Provenance columns + driver-ETA data model deferred (see §5) — needs a migration.
- Exact-time booking is intentionally **windows-only** (matches the existing model); exact
  times map to windows with a polite explanation.
- Same-day cutoff = "no eligible window remains today" (lead-time driven); a separate hard
  order-cutoff time per market is not yet modelled.
- Structured scheduling logs (`temporal_intent_detected`, `past_slot_filtered`, …) are partially
  covered by existing tool logs; a dedicated log set is a small follow-up.

## 8. How to verify manually
1. Freeze the clock: set `MOCK_NOW_ISO=2026-07-28T13:03:00+04:00`.
2. Send "Are you available now to pickup?" → agent offers today's 5–8 PM / 8–10 PM only, does
   not ask the day.
3. Reply "11:30" → agent says it's passed and offers the next window; never asks the day.
4. Send "yesterday" → agent politely declines a past date and offers today/another day.
