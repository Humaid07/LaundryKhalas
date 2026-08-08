# Build Report — WhatsApp Agent Behaviour Corrections

- **Date:** 2026-08-08
- **Design spec:** `docs/superpowers/specs/2026-08-08-whatsapp-behaviour-corrections-design.md`
- **Plan:** `docs/superpowers/plans/2026-08-08-whatsapp-behaviour-corrections.md`
- **Commits (main):** Phase 1 `1504f4c` · Phase 2 `47a3e03` · Phase 3 `9efa32d` · Phase 4 `2725489`

## 1. Task objective
Correct customer-facing WhatsApp-agent behaviour and register the rules in the canonical
source-of-truth so they are loaded at runtime, not just prompt prose: brand = **Laundry
Khalas**; short **1–3 message** replies; **no unnecessary booking CTA**; soft conversion;
a backend-approved **5–7 min discount-objection follow-up**; a **silent conversion
review** when no discount is permitted; and **backend-only pickup slots** (never an
open-ended pickup time).

## 2. What was built (by phase)
- **Phase 1 — rules as loaded source-of-truth + brand.** New versioned `behaviour_rules`
  section (9 rules) in `config/whatsapp_agent_rules.json`; `rules.py` accessors
  (`behaviour_rules`, `behaviour_rule_texts`, `brand_name`); `booking_system_prompt()`
  now **renders the rules from JSON** (the primary Sonnet path previously hardcoded
  them). Dropped the "exactly ONE message" directive; superseded the `select_pickup_time`
  step → `select_pickup_slot`. Normalized the brand to "Laundry Khalas" everywhere
  customer-facing.
- **Phase 2 — segmentation + no-CTA guard.** `services/reply_segmentation.py`
  (`segment_reply` / `finalize_reply`): the model separates messages with a `---` line;
  the backend caps at 3 validated, ordered, non-empty, non-duplicate, non-mid-sentence
  messages. `services/conversion_guard.py`: detects booking CTAs (excluding operational
  questions) and strips a repeated trailing CTA. `_process_reply` delivers the segments.
  Tone avoid-list extended (filler / CTA / exclamation).
- **Phase 3 — discount-objection follow-up + conversion review.** New `DISCOUNT_OBJECTION`
  follow-up type (offset 6 min) scheduled when the agent declines a further discount;
  `services/discount_followup.py` re-runs `negotiation.plan_offer` at send time (the AI
  never picks a number) → send an approved offer / raise a silent review / suppress.
  `services/negotiation_review.py` creates a one-open-per-conversation
  `CUSTOMER_CONVERSION_REVIEW` pending task (no bot pause). `services/hesitation.py`
  gives deterministic price-enquiry vs price-objection signals (§17).
- **Phase 4 — pickup enforcement.** `customer_memory.next_location_ask()` asks for only
  the ONE missing location piece (address vs pin) before backend slots; tests lock the
  prompt's open-ended-time prohibition and backend-slot requirement.

## 3. Why
The agent produced long paragraphs, appended a booking CTA to nearly every answer, used
a mis-spelled brand, and pressured on discount refusals. The rules also lived only in a
hardcoded prompt string on the path that actually serves customers, so they were neither
auditable nor centrally editable.

## 4. Files created
`services/reply_segmentation.py`, `services/conversion_guard.py`,
`services/hesitation.py`, `services/discount_followup.py`,
`services/negotiation_review.py`; tests `test_behaviour_rules.py`,
`test_behaviour_rules_prompt.py`, `test_brand_spelling.py`, `test_reply_segmentation.py`,
`test_conversion_guard.py`, `test_turn_segmentation.py`, `test_hesitation.py`,
`test_discount_followup.py`, `test_discount_objection_followup.py`,
`test_conversion_review.py`, `test_pickup_enforcement.py`.

## 5. Files modified
`config/whatsapp_agent_rules.json`, `config/agent_tone_rules.json`,
`config/followups.json`, `config/pending_tasks.json`, `config/persona.json`,
`config/quick_actions.json`, `config/laundrykhalas_knowledge.json`,
`config/escalation_rules.json`, `config/scenarios/generate_scenarios.py`, `rules.py`,
`agents/whatsapp_agent/booking_tools.py`, `agents/whatsapp_agent/order_flow.py`,
`api/evolution_webhooks.py`, `llm/providers/mock.py`, `services/followups.py`,
`services/followup_scheduler.py`, `services/pending_tasks.py`,
`services/persona_assignment.py`, `services/process_guide.py`,
`services/customer_memory.py`, `db/repositories/scheduled_followups_repo.py`,
`db/repositories/pending_tasks_repo.py`, `scripts/run_due_followups.py`, `pyproject.toml`,
plus updated assertions in `test_agent_prompt_persona.py`, `test_followups.py`,
`test_persona_assignment.py`, `test_reply_style.py`, `test_chat.py`, `test_booking_tools.py`.

## 6. API / behaviour changes
- `negotiate_order_price` at the floor now returns `action: "decline_additional_discount"`
  with a plain decline (was `escalate` with an "I'll get back to you" message).
- New follow-up type `DISCOUNT_OBJECTION`; new pending-task type
  `CUSTOMER_CONVERSION_REVIEW`.

## 7. Database
No migration. Follow-up state (`quote_version`, decision inputs) is stored in the existing
`scheduled_followups.payload` (jsonb); `scheduled_followups_repo.schedule` now writes it.
`pending_tasks_repo.has_open()` added for review dedupe.

## 8. Mock-only / live / deferred
- **Live (dev/test):** all rule loading, segmentation, CTA guard, and the negotiate
  decline path run in the normal agent turn. The discount-objection follow-up + conversion
  review run in the Supabase-only follow-up sweeper (`scripts/run_due_followups.py`).
- **Deferred / documented limitation:** customer-facing pickup slots stay on the static
  `pickup_slots` catalogue; wiring the driver-availability-grounded routing slot generator
  (`routing/slots.py`) into pre-confirmation customer slots is deferred (Tests 18/19 are
  satisfied at the routing-engine layer). `hesitation.py` and `next_location_ask()` are
  tested deterministic utilities; the live Sonnet path currently enforces §11/§17 via the
  rendered rules + `pin_available` memory + the negotiation engine rather than calling
  these helpers directly.

## 9. Security / privacy
No PII exposure changes. Conversion-review notes are Ops-facing only (never sent to the
customer); the customer is not told they were escalated unless a real human takeover
occurs. No secrets touched. No live external calls added (the follow-up sweeper obeys the
existing paused-agent / allow-list send gates and 08:00–22:00 window).

## 10. Tests
- New/updated per-phase unit tests (pure-policy + scripted-fake-Anthropic + prompt-string
  assertions), all green at the focused level: Phase 1 rules/brand/prompt; Phase 2
  segmentation/guard; Phase 3 hesitation/discount-decision/objection-scheduling/review;
  Phase 4 pickup.
- Focused cross-module run after Phase 3: **122 passed**. Routing/slot/driver suite: **83
  passed**.
- **Full backend suite: 1,871 passed, 0 failed** (9 warnings), hermetic (mock LLM, sqlite
  pin) — authoritative run over all four phases.

## 11. Known limitations
- Driver-grounded customer pickup slots deferred (above).
- The no-CTA guard strips a *repeated* trailing CTA (when a recent agent message already
  asked one); a first-time appended CTA relies on the rendered rule + the model. This is
  intentional to avoid over-stripping legitimate operational questions.
- Prod rule reload needs a service restart (`rules.py` lru_cache — unchanged, documented).

## 12. Commands
```
cd apps/whatsapp-agent
.venv/Scripts/python.exe -m pytest -q            # full suite
python scripts/run_due_followups.py              # follow-up sweeper (Supabase mode)
```

## 13. Next recommended step
If desired, wire the driver-availability-grounded slot generator into pre-confirmation
customer slots (needs populated production driver-shift data + advanced routing enabled),
and surface the shadow classifier's hesitation labels into the conversion path.
