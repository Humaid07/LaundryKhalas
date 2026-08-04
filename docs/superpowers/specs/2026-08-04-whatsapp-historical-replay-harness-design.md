# Historical WhatsApp Replay Harness — Design Spec

**Date:** 2026-08-04
**Status:** Approved (design), implementation in progress
**Owner:** WhatsApp Agent module

## 1. Objective

Automatically replay every original **inbound customer** message from the uploaded
WhatsApp chat archive through the **current** LaundryKhalas WhatsApp agent, capture the
new replies + tool calls + workflow state + cost, evaluate them against current rules,
and produce downloadable reports.

The question it answers: *"How would the current LaundryKhalas WhatsApp agent respond if
it received the same customer messages today?"*

## 2. Locked decisions

| Decision | Value | Rationale |
|---|---|---|
| Model | `claude-sonnet-5` (replay override) | Founder request; overrides prod Haiku via **process-scoped env**, prod `.env` untouched. |
| Run size | Full archive, all non-empty chats | Founder request. |
| Cost gate | **Hard stop at $70 USD**; explicit override flag to exceed | Founder: "approve with me first beyond $70". |
| Storage | Supabase **test** project, `replay_*` namespace + dedicated tables + cleanup | Reuses already-seeded catalogue/facilities; no prod DB. |
| Scope | Core end-to-end + CLI + all reports + tests. **Defer** admin dashboard page & model-compare UI. | YAGNI; data shaped so they slot in later. |

## 3. Source archives

- **Primary (authoritative):** `WhatsApp_All_Chats.zip` — located at `C:\Users\HP\Downloads\WhatsApp_All_Chats.zip` (452 MB). HTML export: one folder per contact `+<phone>/<phone>.html`, plus media (`.jpeg`, `.oga` audio, `.mp4`, `.pdf`, `.docx`). 533 conversation HTML files, 506 with inbound, **11,709 inbound customer messages**.
- **Fallback/validation:** `chats_html.zip` (`C:\Users\HP\Downloads\chats_html.zip`, 3.2 MB). Used only when a conversation is missing/unparseable in primary. Prefer primary on duplicates.
- Configurable via `WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH` / `WHATSAPP_REPLAY_FALLBACK_SOURCE_PATH`. If not at configured paths, search repo, Downloads, and configured data dirs before failing. Report final path + structure.

### HTML format (confirmed)
- `__message-in` → **INBOUND_CUSTOMER**; `__message-out` → **OUTBOUND_HISTORICAL_STAFF**.
- Text: `<span ... class="__selectable-text __invisible-space __copyable-text">…</span>`.
- Timestamp: time-only span (`___3EFt_`); date comes from date-separator rows.
- Message id: on the wrapping `<div id=...>`.
- Encoding: bytes contain smart punctuation; decode carefully, preserve exact wording.

## 4. The injection seam (grounded in real code)

`api/evolution_webhooks.py:549` — `async def _process_reply(convo, customer, combined, *, phone, masked, live, last_inbound_msg, turn_id=None)`.
Runs the **full** pipeline (abuse gate → draft load → Claude-orchestration branch → post-confirm guard → history → persona → `BookingContext` → `run_booking_turn` → deliver). Transmits only when `live=True`.

Escalation acks instantiate `EvolutionWhatsAppChannel.from_settings()` **directly** (lines 411/580/840/1039/1055/1086), bypassing any passed channel. Therefore the safety mechanism is **class/factory-level replacement** of `EvolutionWhatsAppChannel` with a capture-only channel — installed before any pipeline import. This satisfies the spec rule "never depend only on the test number; replace the outbound provider with a capture-only adapter."

- Agent turn: `agents/whatsapp_agent/booking_tools.py:825` `run_booking_turn(ctx, *, text, history, max_tokens)` → `(reply_text, LLMResult)`.
- Usage on `LLMResult` (`llm/providers/base.py:54`): `tokens_in/out`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `tool_rounds`, `tool_calls`.
- Model id resolved at `settings.anthropic_model_effective` (priority `ANTHROPIC_WHATSAPP_MODEL → ANTHROPIC_MODEL → LLM_MODEL → default`). Replay sets `ANTHROPIC_WHATSAPP_MODEL=claude-sonnet-5` in-process.
- DB: asyncpg pool (`db/database.py`), Supabase mode required for booking (`is_supabase_mode()`), guarded by `DATABASE_ENV=test` / `SUPABASE_PROJECT_TYPE=test`.
- First-confirm side effects bundle: `services/order_confirmation.apply_post_confirmation_effects` (facility assign + notify + handoff + campaign + CRM). Facility notifications are **mock by default** (`FACILITY_NOTIFICATIONS_MODE=mock`). No live Stripe exists (prompt copy only).

## 5. Module layout — `apps/whatsapp-agent/replay_harness/`

```
archive/  zip_inspector.py, html_parser.py, fingerprint.py, inventory.py
core/     models.py, pii.py, clock.py, config.py
safety/   guard.py, capture_channel.py
runner/   isolation.py, fixtures.py, replay_runner.py
eval/     evaluator.py, divergence.py
report/   html_report.py, csv_report.py, jsonl_report.py, failed_export.py, cost_report.py
cli.py    (python -m replay_harness ...)
```
DB migration `supabase/migrations/000039_replay_harness.sql`: `replay_runs`, `replay_conversations`, `replay_turns`.

## 6. Data model

- `ParsedMessage(source_chat_id, source_filename, source_message_id, timestamp, direction, sender_label, sender_identifier_hash, message_type, text, caption, media_reference, quoted_ref, reply_to_id, location_data, contact_data)`.
- `direction ∈ {INBOUND_CUSTOMER, OUTBOUND_HISTORICAL_STAFF, SYSTEM_EVENT, MEDIA_MESSAGE, UNSUPPORTED_MESSAGE, EMPTY_MESSAGE}`. Only `INBOUND_CUSTOMER` injected.
- `ReplayTurn` capture: `detected_intent, resolved_service, resolved_item, service_code, pricing_type, unit_price, quantity, pre_discount_total, discount_pct, discount_amount, final_total, catalogue_version, missing_fields_before/after, order_state_before/after, pickup_slot_options, selected_pickup_slot, facility_selection_result, human_intervention_status, additional_notes, confirmation_status` + model usage + tool calls. Sourced from **real backend state/tool results**, not inferred from reply text.

## 7. Dedup / fingerprint

Deterministic fingerprint from: customer-identifier hash, first & last inbound timestamp, inbound message count, normalized inbound text hash, source filename. On duplicate candidates: prefer most complete → prefer with media → prefer `WhatsApp_All_Chats.zip`. Record excluded duplicate + reason (`duplicate_conversations.csv`). Uncertain cases marked for review, never silently dropped.

## 8. Safety (fail-closed startup guard)

Refuses to run unless ALL hold: `APP_ENV != production`; `DATABASE_ENV == test`; `SUPABASE_PROJECT_TYPE == test`; `DATABASE_MODE == supabase`; `WHATSAPP_REPLAY_MODE == true`; `WHATSAPP_REPLAY_CAPTURE_ONLY == true`; real-send / real-payment / real-notification / real-facility-dispatch / real-driver-dispatch / production-db-write flags all **false**; capture channel installed AND a probe "send" is verified captured (not transmitted). Any failure → abort before any pipeline import. Modeled on `scripts/_safety.py`.

Env contract:
```
WHATSAPP_REPLAY_MODE=true
WHATSAPP_AGENT_MODE=test
WHATSAPP_REPLAY_CAPTURE_ONLY=true
WHATSAPP_REPLAY_ALLOW_REAL_SENDS=false
WHATSAPP_REPLAY_ALLOW_REAL_PAYMENTS=false
WHATSAPP_REPLAY_ALLOW_REAL_NOTIFICATIONS=false
WHATSAPP_REPLAY_ALLOW_REAL_FACILITY_DISPATCH=false
WHATSAPP_REPLAY_ALLOW_REAL_DRIVER_DISPATCH=false
WHATSAPP_REPLAY_ALLOW_PRODUCTION_DB_WRITES=false
WHATSAPP_REPLAY_REDACT_PII=true
WHATSAPP_REPLAY_TIMING_MODE=ACCELERATED_TIMING
WHATSAPP_REPLAY_TIME_SCALE=0.02
WHATSAPP_REPLAY_MAX_DELAY_SECONDS=3
WHATSAPP_REPLAY_CUSTOMER_MEMORY_MODE=CUSTOMER_HISTORY
WHATSAPP_REPLAY_MAX_CONCURRENCY=5
WHATSAPP_REPLAY_REQUESTS_PER_MINUTE=40
WHATSAPP_REPLAY_MAX_RETRIES=3
WHATSAPP_REPLAY_MAX_COST_USD=70
WHATSAPP_REPLAY_MODEL=claude-sonnet-5
```

## 9. Isolation

Synthetic deterministic identities: `replay_customer_000001`, `replay_conversation_*`, `replay_order_*`. One-way hash of the real number for repeat-customer matching only (never routable). If an E.164-like value is needed internally, generate a non-routable test identity, blocked at transport layer regardless. `ISOLATED_CHAT` vs `CUSTOMER_HISTORY` (default) memory modes. Reset state between unrelated chats. Cleanup script removes all `replay_*` rows.

## 10. Timing / dates / media

- Timing: `ACCELERATED_TIMING` (scale 0.02, max 3s) default; `ORIGINAL_TIMING` optional. Both feed the **real** aggregator so fragments merge exactly as production would.
- Dates: `HISTORICAL_DATE_CONTEXT` (default) via **injectable clock** set to the conversation timestamp (never mutates global system clock); `CURRENT_DATE_CONTEXT` optional. Mode recorded in reports.
- Media: images → current inbound media path; audio → current voice-note fallback→(2nd) human-intervention rule; location → coords used only in-memory, redacted in reports; missing binary → `MEDIA_PRESENT_BINARY_UNAVAILABLE`; never invent media content.

## 11. Evaluation & divergence

Per-turn rule checks → severity `CRITICAL/HIGH/MEDIUM/LOW/INFO` (invented price, wrong total, discount stacking, VAT re-added, duplicate confirm, false pickup confirm, AI reply during takeover, data leakage, real side effect = CRITICAL; wrong service, missed escalation, invented availability, photo wrongly required, repair wrongly rejected, from-price-as-exact, pin ignored, confirm without summary = HIGH; etc.). Historical staff reply shown beside, **never** fed to agent; divergence from it is NOT auto-marked wrong. Divergence categories captured (`CUSTOMER_MESSAGE_DOES_NOT_ANSWER_CURRENT_AGENT_REQUEST`, etc.). Answers depending on missing external state → `INCONCLUSIVE_EXTERNAL_STATE`.

## 12. Outputs — `replay-results/<replay_run_id>/`

`replay_report.html`, `replay_summary.csv`, `replay_turns.csv`, `replay_conversations.jsonl`, `replay_turns.jsonl`, `failed_conversations/{critical,high,medium}/`, `critical_failures.csv`, `archive_inventory.csv`, `archive_parsing_report.json`, `duplicate_conversations.csv`, `unsupported_messages.csv`, `media_mapping_report.csv`, `replay_cost_report.csv`, `replay_cost_summary.json`. Stable run/dataset ids for future model/prompt comparison.

## 13. CLI

`python -m replay_harness`:
- `inspect-archive` — inventory only, no LLM.
- `dry-run [--all|--sample N]` — parse + cost/token/runtime estimate.
- `run --all | --category X | --sample N --seed S | --conversation ID | --limit N | --with-images | --with-audio`.
- `rerun --run-id R [--severity critical]`.
- `compare --baseline R1 --candidate R2`.
Concurrency/RPM/retry with exponential backoff + jitter; per-conversation progress persisted for resume; completed conversations not re-run unless requested.

## 14. Test & run sequence

1. Unit tests (no LLM): archive path resolution, primary preference, fallback, zip traversal safety, HTML parse, direction detection, combined-file dedup, fingerprint, exact-text preservation, timestamp parse, fragment aggregation, media mapping, missing-media, historical-outbound exclusion, capture-only transport, production safety guard, DB isolation, PII redaction, memory isolation, chronological replay, clock injection, tool/state capture, price/discount/pickup/human-intervention eval, divergence detect, resume, cost ceiling, rate limit, report generation, no real Evolution/Meta/Stripe/facility/driver/prod-write.
2. Parser validation run (no LLM).
3. 10-conversation smoke.
4. 25-conversation representative sample.
5. Full archive (all valid) — stop at $70 unless overridden.

## 15. Non-goals (deferred)

Admin dashboard "Replay Testing" page + rerun/cancel buttons + model-compare UI. Data is structured to support them later without rework.
