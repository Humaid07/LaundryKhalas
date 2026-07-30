# Build Report — WhatsApp agent: voice handling, structured notes, location pin, identity, facility handoff

**Date:** 2026-07-30

## Objective
Add, as one integrated change to the existing agent (Evolution + FastAPI + Supabase +
Claude), the five scenarios: (1) unprocessable voice-note → text fallback → human
intervention; (2) structured additional order notes; (3) centralized facility handoff;
(4) typed address + WhatsApp location pin; (5) WhatsApp number + profile-name identity.
Backend stays authoritative; Claude proposes, backend validates/executes.

## Existing components reused (not rebuilt)
- **Human takeover**: `conversations_repo.start_human_takeover/return_to_bot`, `human_takeovers`
  table, `conversations.status='human_takeover'`, and the webhook AI-skip gate. Voice
  escalation reuses this instead of a new intervention system.
- **Idempotency**: `messages_repo.wa_message_seen` (inbound) + `agent_reply_key_seen` (outbound).
- **Phone**: `services/privacy.normalize_e164 / hash_phone / mask_phone`.
- **Confirmation side-effects**: `services/order_confirmation.apply_post_confirmation_effects`
  (already assigns facility + notifies) — the notes-snapshot + handoff serializer plug in here.
- **Facility routing/serializer**: `facility_routing.assign_facility_for_order`,
  `facility_orders_repo.to_facility_read`, `facility_notifications`.
- **Persona** (assistant name) left untouched; **booking FSM** + Claude tool pattern reused.

## Files created
- `supabase/migrations/20260730_000033_voice_notes_location_identity.sql`
- `apps/whatsapp-agent/scripts/apply_voice_notes_location_identity.py` + `verify_...py`
- `apps/whatsapp-agent/services/media_classification.py`
- `apps/whatsapp-agent/services/voice_fallback.py`
- `apps/whatsapp-agent/services/contact_identity.py`
- `apps/whatsapp-agent/services/order_notes.py`
- `apps/whatsapp-agent/services/location_capture.py`
- `apps/whatsapp-agent/services/facility_handoff.py`
- `apps/whatsapp-agent/db/repositories/order_notes_repo.py`
- `apps/whatsapp-agent/tests/test_voice_notes_identity_location.py`

## Files modified
- `channels/evolution_whatsapp.py` — parser classifies media, keeps AUDIO, exposes
  `media_kind` + `location_event`.
- `api/evolution_webhooks.py` — voice-note branch (fallback → escalate → hold), text reset,
  `_handle_unprocessable_voice` + `_send_plain`.
- `db/repositories/conversations_repo.py` — voice-state get/set/reset, `set_handoff_reason`;
  `return_to_bot` now resets voice counters.
- `db/repositories/orders_repo.py` — `_BOOKING_COLS` extended (structured address, location
  capture, notes snapshot, handoff status) + jsonb casts.
- `services/order_confirmation.py` — confirmed-notes snapshot + centralized facility-handoff
  payload persistence.
- `agents/whatsapp_agent/booking_tools.py` — tools `propose_order_note`, `remove_order_note`,
  `get_active_order_notes`; `get_order_summary` shows Additional Notes + pin status; system
  prompt gains the stable voice/notes/identity/address instructions.
- `settings.py` — `FACILITY_SHARE_CUSTOMER_NAME/PHONE/TYPED_ADDRESS/LOCATION_PIN`.
- `api/facility.py` — order-detail route returns grouped `additional_notes` + config-gated
  typed address / location pin.
- `apps/facility-dashboard/lib/api-client.ts` + `app/(app)/orders/[orderId]/page.tsx` —
  grouped "Additional Notes" section.

## Database migration
`000033` (additive + idempotent, RLS deny, rollback documented): new `order_notes` table
(categorized, dedupe_key + partial-unique index, RLS); conversation voice-escalation columns;
order structured-address/location/notes-snapshot/handoff columns; customer identity columns.
Applied via `scripts/apply_voice_notes_location_identity.py`; confirmed by `verify_...py`.
**Not yet applied to dev Supabase in this session (requires DATABASE_MODE=supabase creds).**

## Voice-message handling
Media classified before any model call; audio never reaches Claude. `voice_fallback` decides:
1st distinct → one polite text fallback; duplicate id → ignored; 2nd distinct →
`REPEATED_UNPROCESSABLE_VOICE_MESSAGE` human intervention + handover + pause; escalated/takeover
→ store only. Counters persisted on the conversation (survive restart), counted by unique id,
reset on valid text / release.

## Additional-note extraction
Claude proposes via `propose_order_note`; backend `order_notes` validates (category vocab,
rejects casual/greeting/unverified-promise), de-dupes (dedupe_key), corrects (single-value
categories supersede), removes on request, PATCH never erases on empty, builds the immutable
confirmed snapshot. 12 categories.

## Order-summary
`get_order_summary` returns grouped `additional_notes`, flat note lines, typed address, and
location-pin status; prompt requires showing the Additional Notes section before confirmation.

## Facility-handoff
ONE serializer `services/facility_handoff.build_facility_handoff_payload` — config-gated
customer name/phone/typed-address/pin, grouped notes, items, pickup window, coords; never
margins/tier/rankings/rates/payment/conversation. Persisted on confirm (status + redacted
snapshot + audit); surfaced on the facility dashboard.

## Address & location pin
`location_capture` parses real Evolution location events (never invents coordinates), reports
missing unit fields, and pin status (received/missing/manual_review). Pin drives routing;
typed address is the human pickup detail. New structured columns persist both.

## WhatsApp number & profile name
`contact_identity`: strict E.164 normalization; profile-name validator rejecting device names,
slogans, phone/email/url, emoji/placeholder (Unicode-aware); precedence explicit > confirmed >
valid profile > ask.

## Dashboard changes
Facility dashboard order detail shows grouped Additional Notes + (config-gated) typed address
and pin. **Admin dashboard surfacing (voice/intervention/identity/notes/pin/handoff) is NOT
done in this pass** (admin order detail is mock-gated) — see limitations.

## Tests added / results
- New `tests/test_voice_notes_identity_location.py` — **35 unit tests, all green** (media
  classification, parser media tagging, voice escalation incl. duplicate/2nd/hold/reset,
  E.164 + profile-name validation + precedence/correction, note validate/dedupe/correct/
  remove/snapshot/patch, location capture, facility-handoff incl. privacy config).
- Existing `test_evolution_channel.py` updated for the additive parser fields.
- **Full suite: 1116 passed, 1 failed.** The one failure
  (`test_service_persistence::test_bespoke_wedding_dress...`) is **pre-existing and unrelated**
  — it asserts old "bespoke" behaviour superseded by the 2026-07-29 specialty-routing change;
  none of that test's code path was touched here.
- ruff clean on all changed files; facility-dashboard tsc clean.

## Update (2026-07-30, follow-up) — identity + location persistence wired into the webhook
- **Identity persistence**: the webhook now calls `_persist_identity` after the customer upsert →
  `customers_repo.update_channel_identity` persists `whatsapp_number`, `normalized_contact_number`
  (strict E.164), `contact_number_source=WHATSAPP_SENDER`, `contact_number_verified`,
  `whatsapp_profile_name`, and the profile-derived `customer_name`/source/confidence/requires-
  confirmation — with a SQL guard that NEVER overwrites a `CUSTOMER_PROVIDED`/`CONFIRMED` name.
  `save_customer_name` now records the explicit name via `set_customer_provided_name`
  (CUSTOMER_PROVIDED, keeps the WhatsApp profile name separate). Emits `whatsapp_number_normalized`
  and `whatsapp_profile_name_accepted|rejected` logs.
- **Structured location persistence**: the webhook now calls `_persist_location` when a location
  event/coords arrive → parses via `location_capture` and writes `pickup_latitude/longitude`,
  `location_name`, `location_provider_address`, `location_type`, `location_accuracy`,
  `location_message_id`, `location_source=whatsapp_pin`, `location_received_at`,
  `location_pin_status=received` onto the active draft (enrichment; the normal booking turn still
  runs). Coordinates are only written from a real event. Emits `whatsapp_location_received`.

## Remaining limitations / external dependencies
- **Migration application + live end-to-end** need dev Supabase creds (`DATABASE_MODE=supabase`);
  the hermetic suite runs on SQLite and the Evolution/asyncpg path short-circuits there, so the
  webhook/repo/handoff wiring is covered by import/ruff checks + the tested pure core, not by an
  in-suite live integration test.
- **Admin dashboard** surfacing of the new fields is not implemented.
- **Post-confirmation amendment (scenario 10)** via Claude: `order_notes` supports `is_amendment`
  and the confirmed snapshot is immutable, but a Claude post-confirm amendment tool is deferred
  (post-confirm chatter is currently blocked by the terminal guard).
- No speech-to-text (intentional — text fallback + human intervention, per spec).
