# WhatsApp Agent Behaviour Corrections — Design Spec

- **Date:** 2026-08-08
- **Status:** Approved (design); implementation phased.
- **Scope owner decisions (locked):** phased delivery (4 commits); pickup slots enforced on the **existing static `pickup_slots` catalogue** (not re-wired to driver-availability); brand normalized to **"Laundry Khalas"** everywhere customer-facing; conversion escalation is a **silent Ops review task** (no bot pause).

## 1. Problem

The customer-facing WhatsApp agent must: use the correct brand spelling **Laundry Khalas**; stop producing long single-paragraph replies (allow 1–3 natural WhatsApp messages, max 3); stop appending a booking CTA after every answer; give the customer space; handle discount objections without pressure (decline + optional backend-approved 5–7 min follow-up); never ask an open-ended pickup time (present backend slots); and escalate to a human conversion review when no discount is permitted and the customer keeps objecting. **Crucially, these must live in the canonical rules source-of-truth and be loaded into the runtime prompt — not only in a hardcoded prompt string.**

## 2. Key findings that shape the design (from repo inspection)

1. **There is no `rules.json`.** The canonical file is `config/whatsapp_agent_rules.json`, a **section-keyed object** loaded by `rules.py` (`lru_cache`d; restart-to-reload). No per-rule version/priority schema exists.
2. **The primary Sonnet path does not read the JSON rule files.** `agents/whatsapp_agent/booking_tools.py::booking_system_prompt()` (the live customer path) is a large hardcoded string; only the secondary `agents/whatsapp_agent/prompts.py::build_system_prompt()` reads `whatsapp_agent_rules.json`/`agent_tone_rules.json`. **The fix must make `booking_system_prompt()` render rules from the JSON.**
3. **Reply is one free-form string per turn**, delivered by `_deliver()` (`api/evolution_webhooks.py:423`); the system prompt hard-codes "exactly ONE message". **Multi-message-per-turn is already supported** — `_deliver` can be called repeatedly and sha1(turn_id|state|body) idempotency makes ordered multi-send safe (the FSM path already sends 2).
4. **The agent already presents backend slots and never asks open-ended time.** The FSM (`WAITING_FOR_PICKUP_SLOT`) and Claude tool path present slot buttons from the static `pickup_slots` catalogue (`slots_repo` + `pickup_availability`) and reject free text. The only residual is the stale `booking_flow.steps: "select_pickup_time"` rule string.
5. **Backend-controlled discount engine exists:** `services/negotiation.py::plan_offer()` returns `offer_ladder|offer_floor|ask_itemisation|escalate|inactive|invalid` with a ceiling (last ladder rung) and facility floor; the AI never picks a number. `escalate` = ceiling/floor reached → the conversion-review trigger.
6. **Scheduler exists:** `scheduled_followups` (dedupe_key, statuses PENDING/SENT/CANCELLED/SUPPRESSED, `payload jsonb`, send-time `SuppressionContext` re-check via `scripts/run_due_followups.py`). A **`QUOTE_INACTIVITY` follow-up already fires at 6 min**. `cancel_for_conversation` already cancels PENDING rows on customer reply.
7. **Classifier (shadow, live model)** already emits `PRICE_ENQUIRY` vs `PRICE_PUSHBACK` vs `DISCOUNT_REQUEST`, `frustration_level` 0–3, sentiment; runs before the agent. Its routing output is currently ignored.
8. **Human review patterns exist:** `pending_tasks` (`pending_tasks_repo.create`, `config/pending_tasks.json` SLA, `TASK_TYPES`) for a silent Ops task; `human_interventions` (one-active-per-conversation) for a bot-pausing takeover. We use `pending_tasks` for conversion review.
9. **Driver-availability-grounded slot generation exists but is dormant** (`services/routing/slots.py::earliest_slot` + `services/routing/availability.py`), used only post-confirmation by the advanced routing engine (default `OFF`; production driver-shift data thin). It is **not** wired to customer slots.

## 3. Non-goals / invariants (must NOT change — §24)

Published prices, facility fees, markup rules, discount ceilings/eligibility, minimum-order, photo rules, payment/Stripe/cash rules, service definitions, repair rules, complaint/refund human escalation, facility routing weights, Express pricing/eligibility, customer-memory rules. New behaviour sits on top. No pre-confirmation re-wire of the routing engine in this task.

## 4. Architecture

### 4.1 Canonical rules (source of truth)
Add a versioned section to `config/whatsapp_agent_rules.json`:

```json
"behaviour_rules": {
  "_note": "Canonical WhatsApp-agent behaviour rules. Rendered into the live Sonnet system prompt via rules.behaviour_rule_texts(). Bump version+updated_at on change.",
  "version": "2026-08-08.1",
  "updated_at": "2026-08-08",
  "rules": [
    { "id": "WHATSAPP_BRAND_NAME", "category": "brand", "priority": 100, "active": true,
      "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "The brand is exactly \"Laundry Khalas\". Always write it as \"Laundry Khalas\" — never \"Laundry Khalaas\" or any other spelling.",
      "params": { "brand_name": "Laundry Khalas" } },
    { "id": "WHATSAPP_RESPONSE_LENGTH", "category": "style", "priority": 90, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "Keep replies short and easy to scan — one idea at a time, no walls of text, no unnecessary explanations." },
    { "id": "WHATSAPP_RESPONSE_SEGMENTATION", "category": "style", "priority": 89, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "A reply may be 1, 2, or at most 3 short WhatsApp messages. Use 1 when the answer is naturally short; split only when it genuinely improves readability. Never split a tiny answer. Separate intended messages with a line containing only ---.",
      "params": { "max_segments": 3, "delimiter": "---" } },
    { "id": "WHATSAPP_NO_UNNECESSARY_CTA", "category": "conversion", "priority": 88, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "Do not end normal answers with a booking/conversion question (\"Would you like to proceed/book?\"). Answer what was asked, then stop. Only ask a question when the information is genuinely needed for the next operational step." },
    { "id": "WHATSAPP_SOFT_CONVERSION_STYLE", "category": "conversion", "priority": 87, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "Convert intelligently but never pressure. Be helpful, calm, confident and low-friction — never desperate, repetitive, pushy or sales-heavy. Ask at most one necessary question per turn." },
    { "id": "WHATSAPP_DISCOUNT_FOLLOWUP", "category": "conversion", "priority": 80, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "If a customer asks for a discount that is not available now, say so plainly and stop — no CTA. A single follow-up may be sent about 5–7 minutes later ONLY if the backend discount engine approves one. Never invent a discount or pick a percentage.",
      "params": { "followup_min_minutes": 5, "followup_max_minutes": 7 } },
    { "id": "WHATSAPP_PICKUP_SLOT_SELECTION", "category": "pickup", "priority": 79, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "Pickup slots come from the backend. Collect the pickup address and location pin first, then present the actual available slots and let the customer choose one." },
    { "id": "WHATSAPP_NO_OPEN_ENDED_PICKUP_TIME", "category": "pickup", "priority": 78, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "Never ask the customer what pickup time they want. The customer never invents a time — they choose from backend-provided slots. If no slot fits, offer the next available date." },
    { "id": "WHATSAPP_HUMAN_CONVERSION_ESCALATION", "category": "conversion", "priority": 70, "active": true, "version": "2026-08-08.1", "updated_at": "2026-08-08",
      "text": "When no further discount is permitted and the customer keeps objecting, do not invent an offer. The team is flagged internally for a conversion review; keep your reply natural and do not tell the customer they have been escalated unless a human actually takes over." }
  ]
}
```

`rules.py` gains: `behaviour_rules()` (section), `behaviour_rule_texts()` (active rules, priority-desc, list of `text`), `brand_name()` (top-level `brand_name`). Top-level `brand_name` becomes `"Laundry Khalas"`.

`booking_system_prompt()` renders a `Behaviour rules (authoritative):\n- …` block from `behaviour_rule_texts()`, **replacing** the hardcoded "exactly ONE message"/style/CTA/pickup lines. `build_system_prompt()` already reads brand/tone and picks up the fixes.

### 4.2 Response segmentation (`services/reply_segmentation.py`)
`segment_reply(text, *, max_segments=3, delimiter="---") -> list[str]`: split on a line that is only the delimiter; trim; drop empty/whitespace/one-word fragments; dedup identical adjacent segments; **merge a segment into the previous one if it would be a mid-sentence split** (previous doesn't end with sentence punctuation or next starts lowercase); cap to `max_segments` by merging the overflow into the last kept segment. If no delimiter present → `[text]`. `_process_reply` replaces the single `_deliver` call with a loop over the returned segments (each its own `BookingReply`, existing idempotency handles order/dedup). Empty-reply guard + `next_step_prompt` substitution stay upstream in `run_booking_turn`.

### 4.3 Conversion / CTA guard (`services/conversion_guard.py`)
Pure helpers: `is_conversion_cta(text) -> bool` (matches "would you like to proceed/book", "shall I book", "go ahead", "arrange (a) pickup?", etc., excluding operational questions), `recent_cta_count(recent_agent_texts) -> int`, `strip_trailing_cta(text) -> str`. In `_process_reply`: derive `recent_conversion_cta_count` from recent `sender_type='agent'` messages (already loaded), inject a dynamic-state hint ("You have already asked to book recently; do not ask again"), and strip a trailing CTA when the turn is an info answer with no operational need (no missing required slot / no quote-approval). Necessary questions (address, pin, slot choice, quote approval) are never stripped.

### 4.4 Discount objection + 5–7 min follow-up (Phase 3)
- New follow-up type **`DISCOUNT_OBJECTION`** (`services/followups.py` constant + template; `config/followups.json` offset `6`, added to `priority`). Scheduled when the agent declines a discount / detects price-pushback and the customer is silent, via `followup_scheduler.build_row` + `scheduled_followups_repo.schedule` (dedupe_key `conv:DISCOUNT_OBJECTION:anchor` → idempotent). `payload jsonb` stores `trigger_message_id`, `quote_version`, `pricing_snapshot_id`, `trigger_type`.
- **Send-time recheck** in `scripts/run_due_followups.py` / `services/followups.py` suppression: for `DISCOUNT_OBJECTION`, call `negotiation.plan_offer(current order state)`. If it yields `offer_ladder`/`offer_floor` → send the **backend-approved** offer message (AI supplies no number). If `escalate`/`inactive`/none, or `quote_version` changed, or order confirmed/paid/cancelled, or under takeover, or opted out, or outside messaging window → suppress (record specific `suppressed_reason`). No AI-chosen discount.
- **Status mapping (no migration):** existing `PENDING/SENT/CANCELLED/SUPPRESSED` + `suppressed_reason`/`cancelled` capture the spec's granular `CANCELLED_CUSTOMER_REPLIED / CANCELLED_ORDER_CHANGED / CANCELLED_HUMAN_TAKEOVER / CANCELLED_NO_LONGER_ELIGIBLE`. Spec fields `trigger_message_id/quote_version/pricing_snapshot_id/followup_type` live in `payload`.
- Existing `cancel_for_conversation(convo, reason="customer_replied")` (called every customer turn) already cancels the PENDING follow-up (§8, Test 7).

### 4.5 Conversion review (`CUSTOMER_CONVERSION_REVIEW`) (Phase 3)
Add to `pending_tasks` `TASK_TYPES` + `config/pending_tasks.json` (SLA). Created (silent, **one-active-per-conversation** dedupe: query open CUSTOMER_CONVERSION_REVIEW for the conversation before insert) when `plan_offer` returns `escalate` while the customer keeps objecting. `notes` carry internal context: customer/order id, service, current customer price, existing discount, max permissible discount, facility cost (audit-authorized), recent customer messages, hesitation reason, conversation state. Reason ∈ `DISCOUNT_LIMIT_REACHED | PRICE_OBJECTION_MARGIN_LIMIT | CUSTOMER_CONVERSION_REVIEW` (stored in `escalation_rule`/subtype). No bot pause; no "I've escalated you" to the customer.

### 4.6 Hesitation (`services/hesitation.py`) (Phase 3)
Deterministic helpers so scheduling is testable without the live classifier: `is_price_enquiry(text)` (don't schedule) vs `is_price_objection(text)`/`negotiation.detect_discount_request(text)` (schedule). Complements the shadow classifier's `PRICE_ENQUIRY`/`PRICE_PUSHBACK`/`DISCOUNT_REQUEST` labels; the classifier remains shadow.

### 4.7 Pickup enforcement (Phase 4)
Address+pin-first using `customer_memory.shape_saved_address().pin_available` — ask only the missing piece (§11). Present static-catalogue slots via existing `pickup_availability.get_availability`; `next_available_date` fallback (§14). The slot "which works better?" is a *necessary* CTA (allowed). Supersede handled in Phase 1.

## 5. Phasing (one commit each)

- **Phase 1** — rules section + `rules.py` accessors + `booking_system_prompt()` rendering + brand normalization + supersede pickup-time step. Tests: brand present/typo absent, all 9 rules load & render, old step gone (1, 24, 25, 26).
- **Phase 2** — `reply_segmentation.py` + `_process_reply` loop + `conversion_guard.py` + tone avoid-list + prompt directive change. Tests: 2, 3, 4, 20, 21, 22.
- **Phase 3** — `DISCOUNT_OBJECTION` follow-up + send-time recheck + `CUSTOMER_CONVERSION_REVIEW` pending-task + `hesitation.py`. Tests: 5, 6, 7, 8, 9, 10, 11, 23, 27, 28.
- **Phase 4** — pickup enforcement + tests: 12, 13, 14, 15, 16, 17, 21, 22.

## 6. Test strategy
Follow existing pure-policy harnesses (no live LLM/DB): prompt-injection asserted via `booking_system_prompt()`/`build_system_prompt()` string presence (like `test_scenarios_regression.py`, `test_agent_prompt_persona.py`); segmentation/guard/hesitation via direct pure-function unit tests; follow-up scheduling/suppression via the `test_followups.py`/`test_followup_scheduler.py` pattern (config `reload_config`, market-tz `_at`); discount decisions via `negotiation.plan_offer` (like `test_negotiation.py`). End-to-end agent behaviour via the scripted-fake-Anthropic harness in `test_booking_tools.py` where needed.

## 7. Documented limitation / deferred
Per the chosen scope, customer-facing pickup slots stay on the static `pickup_slots` catalogue. **Spec Tests 18/19** (facility/driver-unavailable → slot excluded / reroute to another eligible facility) are satisfied at the **routing-engine layer** (`routing/slots.py` + `routing/availability.py`, which already honor driver availability), not the customer-slot layer. Wiring the driver-availability-grounded generator into pre-confirmation customer slots is deferred (documented follow-up), gated on populated production driver-shift data and enabling advanced routing.

## 8. Rollout / operational notes
`rules.py` is `lru_cache`d → a service restart is required for JSON edits to take effect (existing behaviour, documented in the file `_note`). No DB migration is introduced by this work. `DISCOUNT_OBJECTION` follow-ups obey the existing 08:00–22:00 messaging window and paused-agent/allow-list send gates.
