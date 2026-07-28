# Build Report — Refund requests always route to a human (durable AI pause)

**Date:** 2026-07-28
**Scope:** Focused safe slice (agreed with owner) — close the core SAFETY gaps
without a new migration or heavy edits to files a concurrent session is editing.

## Objective
A customer asking for a refund must never be handled entirely by the AI. On a
genuine refund request the AI acknowledges once, a human-intervention record is
created, automation is **durably** paused, and Operations takes over from the
dashboard. The AI must not approve/reject/promise/quote/process a refund.

## Audit (what already existed)
Refund messages already escalated via `detect_escalation → "refund"`: flag
(`refund_request`, urgent, Finance) + ticket + structured **complaint** +
`AWAITING_COMPLAINT_REVIEW` task + one empathetic ack + the current turn's AI
reply cancelled. **Gap:** the AI was **not durably paused** — only the current
turn was cancelled; the customer's *next* message could still hit escalation-again
or the booking/Anthropic flow. No idempotent refund notice; no refund-specific ack.

## What was implemented
1. **Durable pause on refund** (`api/evolution_webhooks.py`) — when
   `category == "refund"`, after creating the flag/ticket/complaint the backend now
   calls `conversations_repo.start_human_takeover(...)` → `conversations.status =
   human_takeover` + `human_intervention_required = true`. Every LATER message is
   then held (store-only) by the existing paused-conversation guard until an
   authorised human release. Order matches the spec: create case → **pause** →
   send the one acknowledgement.
2. **Idempotent handover** — a new guard at the top of the escalation block: if the
   conversation is already `human_takeover`, the inbound is stored for the operator
   and NO second flag/complaint/notice is created and the model never runs
   (`refund_notice_duplicate_prevented`). The `human_takeover` status is the
   idempotency key (one notice per takeover).
3. **Approved refund acknowledgement** — `_REFUND_ACK_TEXT` ("…forwarded your refund
   request to our Operations team… one of our executives will get in touch"), sent
   once instead of the generic complaint ack; stored with
   `metadata.kind=refund_ack` + an idempotency key.
4. **Broader refund detection** (`config/escalation_rules.json`) — added "money
   back / reverse the payment / paid twice / return the amount / charged
   incorrectly / …" so the spec's refund phrasings are recognised.
5. **Prompt hardening** (`booking_system_prompt`) — an explicit refund clause:
   never approve/reject/calculate/process a refund, never promise amount/method/
   time, stay paused after handover, never claim a refund is complete without a
   verified backend record. (Defence-in-depth: refunds already short-circuit
   deterministically BEFORE any model call.)
6. **Release path** already exists (`conversations_repo.return_to_bot` → status
   `bot`, ends takeover) — the authorised human explicitly releases; the next
   message is processed fresh (no stale refund ack).

## Logging (safe ids only, no PII/phones/secrets)
`refund_intent_detected`, `refund_human_intervention_created` (reason=REFUND_REQUEST),
`refund_notice_sent`, `refund_notice_duplicate_prevented`, plus the existing
`evolution_inbound_held`.

## Files changed
`api/evolution_webhooks.py`, `agents/whatsapp_agent/booking_tools.py` (prompt),
`config/escalation_rules.json`; new `tests/test_refund_intervention.py`.

## Tests + results
- `test_refund_intervention.py` — **18 passed**: refund-language detection coverage
  (all spec phrasings), non-refund messages not flagged, and the acknowledgement is
  safe (contains Operations/review; contains none of approved/processed/eligible/
  "you will receive"/"3 days"/"AED "/against-policy).
- Regression: `test_complaints.py` + `test_agent_rules.py` + refund = **60 passed**. ruff clean.
- **Live end-to-end vs Supabase** (real webhook): 1st refund → `refund_intent_detected`
  + `refund_human_intervention_created`; conversation → `human_takeover`,
  `human_intervention_required=true`, exactly **1** refund flag; 2nd refund →
  `refund_notice_duplicate_prevented` (held, no 2nd ack); a normal booking message
  while paused → `evolution_inbound_held (human_takeover)` (AI not invoked). Released
  + cleaned up.

## Manual verification
From an allow-listed number send "I want a refund" → the agent replies once with the
Operations-handover notice and the conversation flips to human_takeover in the
dashboard inbox (flag + complaint + review task). Any further messages are held for
the operator; the AI does not reply until a human clicks Return to bot / release.

## Honestly deferred (NOT in this slice — with reasons)
- **Dedicated `refund_cases` table + `refunds_repo` + refund_type/status taxonomy** —
  needs a new migration (`000028`); deferred to avoid colliding with the concurrent
  session's migration numbering. Refunds currently ride on the existing flag +
  structured complaint records (which already carry order/category/description).
- **Dashboard Refunds queue + `refunds.*` permissions** — the case already appears in
  the existing Human-Intervention inbox (flag + complaint + `human_takeover`); a
  dedicated Refunds section + refund-specific RBAC (separate Next.js app) is a follow-up.
- **Provider refund processing (approve/reject/process, Stripe refund IDs,
  refundable-balance/idempotency)** — Stripe is not integrated (mock/off, CLAUDE.md
  §5); real refund execution is out of scope / requires approval. Not faked.
- **Refund-tool set** (`classify_refund_intent`/`create_refund_case`/…) — the
  detection + handover are deterministic backend logic (safer than model-driven);
  the case-creation tools are deferred with the refund_cases model.
- No CRM/HubSpot added; all data stays in the Laundry Khalaas backend/DB/dashboard.

## Known limitation
The acknowledgement is stored only on a successful Evolution send (same pattern as the
complaint ack); if the send fails the pause + flag still persist but no ack row is
written. Refund detection is deterministic keyword-based, so an unusual paraphrase with
no refund/charge keyword (e.g. "you took AED 300 instead of 200" with no keyword) may
not trigger — extend the keyword list as such cases appear.
