# Facility Quotation + Photo-Optional Booking + Feedback-Aware Memory — Design

**Date:** 2026-08-06
**Status:** Approved to build (user: build fully before manual test). Extend existing
workflows — no new WhatsApp agent, no CRM, no parallel quotation system.

## 1. Objective
Photos never block eligible pickup; a clear provisional→facility-quote→markup→customer-approval
workflow reaches the assigned Facility Dashboard; every order/item/quote/photo/approval is isolated;
the agent captures feedback + confirmed customer preferences into a validated durable memory store, and
never self-trains or changes global behaviour without authorized review.

## 2. Ground truth (extend, don't duplicate)
- Photo policy = single boolean `service_rules.ServiceRule.photo_required` (category/keyword). → widen to
  a 5-level `photo_policy`.
- Quote scaffold: `facility_quote_revisions` (table + `services/quote_revision.py` state machine + repo +
  `api/internal_quote_revisions.py`), `pending_tasks(AWAITING_FACILITY_QUOTE, quote_id)`, `facility_issues`
  (`requires_photo/requires_customer_response/order_item_id`). → extend into the quote-request lifecycle.
- Markup: `facility_pricing.apply_margin` + `facility_pricing_repo.get_margin_rule`; `facility_cost`
  returns None→PENDING when unpriced. `quote_revision.compute_customer_price` already reuses apply_margin.
- Customer memory: `services/customer_memory.py` pure/derived, NO store, no provenance/PATCH. → add a
  real `customer_memory` + `customer_memory_history` table/repo with scope+confidence+PATCH.
- Classifier: `whatsapp_message_classifications` has `corrected_*` columns (feedback attaches here).
- Media: `order_photos` has `order_item_id/source/caption` (added mig 000046); facility handoff firewall.
- Prompt: stable `prompts.py::build_system_prompt()`; behavioural guidance in
  `agents/whatsapp_agent/booking_tools.py`; dynamic memory injected as `returning_customer_memory` AFTER
  the cache breakpoint (context_assembly). No multi-active-order resolver exists.
- Latest migration 000049 → next **000050**.

## 3. Decomposition (staged areas)
- **A. Photo policy + provisional pricing (pure).** 5-level `photo_policy` on `ServiceRule` (+ derivation);
  `services/provisional_pricing.py` — pricing states (PUBLISHED_EXACT/FROM/RANGE, PROVISIONAL_ESTIMATE,
  AWAITING_FACILITY_QUOTE, FACILITY_QUOTE_RECEIVED, CUSTOMER_PRICE_*, QUOTE_EXPIRED) + customer-facing
  "starts from"/range/provisional presenter (grounded; never calls provisional "final"). Unit tests.
- **B. Quote-request workflow + markup (DB).** Migration 000050: extend `facility_quote_revisions` with
  `pricing_state, quote_version, provisional_minimum/maximum, photo_status, inspection_status, expires_at`
  + the fuller request status set; new `customer_quote_snapshots` (immutable calc) + `customer_quote_approvals`.
  Reuse `apply_margin`. `services/facility_quote_workflow.py` orchestration + repos. Operations-review gate
  (config: above-amount / luxury / restoration / wedding / below-margin). APIs (facility submit + ops review
  + send-to-customer). Isolation: every query filters `(order_id, order_item_id, quote_version)`.
- **C. Customer memory store + feedback (DB).** Migration: `customer_memory`, `customer_memory_history`,
  `customer_feedback_events`, `feedback_review_actions`, `global_rule_change_candidates`,
  `order_context_links`. `services/customer_memory_store.py` (scope CUSTOMER_GLOBAL/ADDRESS/SERVICE/ORDER_ONLY,
  PATCH semantics — null never erases, correction supersedes + history), `services/customer_feedback.py`
  (detect + classify feedback type, customer-specific vs global). Controlled backend ops
  (`save_confirmed_customer_memory`, `invalidate_customer_memory`, `create_customer_feedback_event`,
  `classify_feedback_scope`, `queue_global_feedback_review`, `approve_feedback_rule_change`). Tests.
- **D. Media + order-context isolation.** `order_context_links`; `resolve_message_order_context` (explicit
  id → active workflow → most-recent active → quoted-item/payment/issue ref; ambiguous → one question);
  `link_media_to_order` (never auto-reuse across orders). Tests.
- **E. WhatsApp agent wiring.** Prompt §27 additions (photo-optional, provisional-not-final, per-order
  isolation, ask-which-order, backend-validated memory, no self-training). booking_tools photo-request →
  once + policy-driven; provisional price wording; facility-confirmed price relay + approval question.
  Backend memory tools exposed to the agent (validated, backend-authoritative).
- **F. Dashboards.** Facility Dashboard quote card (Required Work→Notes→Photos→Items→Inspection→Facility
  Quote→Issues→Actions, ack gate, "customer photo not provided", submit-quote) — extend the Area-2 order
  view. Operations: quote-review + feedback-review sections.
- **G. Audit events + full test matrix + docs.**

## 4. Guardrails
Claude never invents a price/fee/markup/facility-response/inspection/approval/photo/order-detail. Backend
authoritative for all pricing/approval/memory. Provisional ≠ final. Facility never sets customer price;
customer never sees facility fee/markup/competing quotes. Memory: null never erases; ORDER_ONLY never
influences another order; global feedback needs authorized review (no auto prompt/rule/model change).
Idempotency: UNIQUE(order_id,order_item_id,quote_version); UNIQUE(facility_id,quote_request_id,facility_quote_version);
UNIQUE(provider,provider_message_id,feedback_type). Every order isolated.
