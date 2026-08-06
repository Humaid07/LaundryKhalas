# Week 05 Report — Facility Order Experience Redesign

**Week of:** 2026-08-06

## 1. Executive summary
Redesigned the Facility Dashboard order cards and detail view and wired them to real backend data so a facility can, at a glance, see exactly what work an order needs, which notes and photos matter, and the next action — without opening multiple pages or reading the WhatsApp conversation. Delivered end-to-end across six areas: a centralized PII-safe order-view serializer, deterministic "Required Work", prioritized notes, per-item details, per-item photo linking, a versioned review-acknowledgement gate, an 18-type raise-an-issue flow, clarification amendments, and a facility→Ops→customer revised-quote workflow.

## 2. What shipped this week
Card + detail redesign (hierarchy: Required Work → Important Notes → Photos → Items → Pickup → Fee → Issues → Actions); review-acknowledgement (versioned, gates Start Processing on both frontend and backend); raise-an-issue redesign with item link + photo attach surfacing into the Ops dashboard, with a "pause the stage" gate; clarification answers recorded as audit-preserving order amendments; revised-quote workflow with deterministic backend margin calc and a customer-approval gate that never exposes facility fee/margin.

## 3. What changed since last update
The facility order list/detail now render from a structured `view` payload instead of ad-hoc fields; 3 additive migrations; new Ops surfaces for issue photos and quote review.

## 4. Screens/features ready to demo
Facility order list (redesigned cards), order detail (acknowledge gate, photo lightbox, item breakdown, revised quote), raise-issue with photo; admin facility-issue detail (photos, requirement chips, revised-quote review, clarification recording).

## 5. Backend progress
6 new pure/service modules, 2 new repos, 1 new Ops router, 3 migrations; every facility read scoped by `facility_id`; deterministic Required Work + price calc (no LLM).

## 6. Frontend progress
Redesigned card + detail; reusable photo viewer/lightbox, view sections, general-photo linker, raise-issue form, quote-revision panel; admin issue-detail extended. Both apps `tsc` + `eslint` clean.

## 7. Agent progress
No agent behavior changed; all facility-facing content is grounded in structured data.

## 8. Database progress
New `facility_order_reviews`, `facility_quote_revisions`; extended `order_notes`, `order_photos`, `orders`, `facility_issues`. Migrations 000046–000048 authored (apply pending).

## 9. Security/privacy progress
Payload whitelists fields (no margin/Stripe/other-facility rates/customer amount/conversation); customer fields gated by FACILITY_SHARE_*; photos Bearer-guarded/signed; facility fee never on a customer path; immutable per-order fee snapshot.

## 10. Testing progress
11 new backend test files (~90 tests) green in targeted runs; both frontends typecheck + lint clean. Full backend suite green apart from the **pre-existing seed-isolation race** (10 tests, unrelated — confirmed via isolation reruns).

## 11. Blockers
None. Live E2E needs migrations 000046–000048 applied + the Docker/Evolution/Supabase stack.

## 12. Risks
`facility_fee_snapshot` is not yet populated at handoff, so per-item/total facility fee shows once that wiring lands; until then finance shows the fee where present.

## 13. Decisions needed from founder/team
Confirm the default platform margin used to compute customer-facing revised prices (currently 30% when no rule is supplied), and whether a live customer-approval channel is in scope next.

## 14. Deviations from roadmap/spec
`facility_issue_media` modeled via `facility_issues.photo_ids` + the unified `order_photos` table (source=FACILITY_ISSUE) rather than a separate table; card shows a thumbnail strip (not full galleries) for list performance. Both noted in the spec.

## 15. Next week's plan
Populate `facility_fee_snapshot` at facility handoff; apply migrations on dev/test Supabase; run a live E2E pass and capture demo screenshots; add item-level pause granularity if needed.
