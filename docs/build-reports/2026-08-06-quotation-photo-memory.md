# Build Report — Facility Quotation + Photo-Optional Booking + Feedback-Aware Memory

**Date:** 2026-08-06

## Existing components reused
`service_rules.py` (§17 registry), `facility_quote_revisions` (+ `quote_revision.py` state machine +
repo + `internal_quote_revisions` API), `pending_tasks(AWAITING_FACILITY_QUOTE)`, `facility_issues`,
`facility_pricing.apply_margin` + `facility_pricing_repo.get_margin_rule`, `facility_cost` (None→PENDING),
`money.py`, `order_photos` (item_id/source/caption), `facility_notifications`, `customer_memory.py`
(derived context), classifier `corrected_*` columns, the facility order-experience dashboard
(`QuoteRevisionPanel` = facility quote submission), Evolution webhook `_process_reply`, the agent tool
loop in `booking_tools.py`.

## Files changed
Backend new: `services/{provisional_pricing,quote_pricing,customer_feedback,customer_memory_store,
customer_memory_service,customer_feedback_service,order_context,facility_quote_workflow}.py`,
`db/repositories/{customer_memory_repo,customer_feedback_repo,customer_quote_repo}.py`,
`api/internal_feedback.py`. Backend modified: `services/service_rules.py` (5-level photo_policy),
`agents/whatsapp_agent/prompts.py` (§27), `agents/whatsapp_agent/booking_tools.py` (photo-optional
guidance + `save_customer_preference` tool), `api/evolution_webhooks.py` (feedback capture), `main.py`.
Frontend: `apps/admin/lib/dashboard/whatsapp-agent-api.ts` (+FeedbackEventDTO/methods),
`apps/admin/app/admin/feedback/page.tsx` (new), `apps/admin/components/layout/AdminSidebar.tsx` (nav).

## Database migrations
`20260806_000050_quotation_memory_feedback.sql` (**applied**): extended `facility_quote_revisions`
(versioned/provisional lifecycle); new `customer_quote_snapshots`, `customer_quote_approvals`,
`customer_memory` (+history), `customer_feedback_events`, `feedback_review_actions`,
`global_rule_change_candidates`, `order_context_links` — with the spec's idempotency uniques
(`UNIQUE(order_id,order_item_id,quote_version)`, `UNIQUE(provider,provider_message_id,feedback_type)`).

## Photo-optional booking changes
5-level `photo_policy` on `ServiceRule` (`derive_photo_policy`; invariant `photo_blocks_pickup()==False`).
`booking_tools` specialty/bespoke guidance rewritten: ask a photo ONCE, never block pickup, give an
approved starting price/range, "exact price confirmed after the facility checks the item", continue the
pickup. §27 prompt reinforces it. Old photo-gate test updated.

## Provisional-price changes
`provisional_pricing.py`: 11 pricing states + a customer-facing presenter (published exact/from/range,
provisional estimate, awaiting-facility-quote, facility-confirmed-final) — provisional is never called
"final"; a range never guaranteed unless a backend maximum exists.

## Facility quote-request workflow
Extends `facility_quote_revisions` (no parallel system). `facility_quote_workflow.price_facility_quote`:
validate fee → `calculate_customer_price_from_facility_quote` (reuses `apply_margin`) → immutable
`customer_quote_snapshots` → Operations-review gate (above-amount/luxury/restoration/wedding/below-margin).
Versioned, idempotent `customer_quote_approvals` (old approval never approves a new version).

## Facility Dashboard / notification changes
Facility quote submission reuses `QuoteRevisionPanel`; the Area-2 order card already shows Required Work /
notes / photos / "customer photo not provided" state / ack-gate. Facility notification reuses
`facility_notifications` (mock-first, dedupe).

## Markup calculation changes
`quote_pricing.calculate_customer_price_from_facility_quote` — backend-authoritative, immutable snapshot;
Claude never computes markup; facility fee + markup stripped on customer paths (`snapshot_to_read`).

## Customer WhatsApp quote flow / approval
Backend workflow complete (submit → price → ops-review → approve). §27 prompt instructs the agent to relay
a backend-confirmed price briefly + one approval question. (The live outbound customer relay as an agent
tool is a remaining wiring item; the decision store + state machine are done.)

## Order & media isolation
`order_context.resolve_order_context` (explicit → single-active → ambiguous asks ONE question) +
`link_media_to_order` (`order_context_links`; no auto cross-order reuse). §15/§16/§17 enforced.

## Customer-feedback collection
`customer_feedback.detect_feedback` (11 types, customer/global scope) + capture at the Evolution webhook
(best-effort, idempotent per provider message). Global feedback is queued, never auto-applied.

## Customer-memory implementation
Durable `customer_memory` (+history) with PATCH (`customer_memory_store`): null never erases, unconfirmed
guess rejected, correction supersedes + history, ORDER_ONLY never leaks. Controlled ops
`save_confirmed_customer_memory` / `invalidate_customer_memory`; exposed to the agent via the
`save_customer_preference` tool.

## Global feedback-review workflow
`api/internal_feedback.py` + admin **Feedback Review** page: list, approve-as-customer-memory,
queue-global (versioned rule-change candidate), reject. Unreviewed global feedback never changes
production behaviour.

## Tests added / results
`test_photo_policy_provisional.py`, `test_quote_pricing_memory_feedback.py`,
`test_memory_feedback_context.py`, `test_facility_quote_workflow.py` (+ updated
`test_scenarios_regression.py`). ~60 new backend tests, all green; agent/webhook/orders suites green
(68 passed in the final combined run); admin tsc + lint clean.

## Remaining limitations
Live outbound facility-confirmed-price relay + customer-approval capture as agent tools (backend + prompt
ready); Facility Dashboard "Inspection Details / Facility Quote" card polish; the full §31 test matrix
(core covered, not exhaustive); some §30 audit-event names; a build/live E2E of the full quote loop.
