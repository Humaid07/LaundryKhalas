# Build Report — Facility Order Experience Redesign

**Date:** 2026-08-06

## 1. Build title
Facility Dashboard order card + detail redesign with full backend integration (comprehension → issues → clarifications → revised quotes).

## 2. Task objective
Let every facility instantly understand what an order contains, what work must be done, which notes/photos matter, and the next action — without opening multiple pages, reading raw JSON, or reading the WhatsApp conversation. Deliver it end-to-end on real order data, reusing the existing design system, auth, permissions, APIs and models.

## 3. What was built
A centralized, PII-safe facility order-view serializer and a redesigned card + detail view following a fixed visual hierarchy (Required Work → Important Notes → Photos → Items → Pickup → Fee → Issues → Actions), plus four workflows: **review-acknowledgement** (versioned, gates Start Processing), **raise-an-issue** (18-type registry + item link + photo attach + Ops surfacing + stage pause), **clarification** (customer answer → order amendment), and **revised-quote** (facility fee → Ops margin calc → customer approval). Built across 6 sequential areas.

## 4. Why it was built
The prior card showed only id/service/status/time; work instructions, notes and photos were buried or absent, forcing facilities to guess or chase Operations.

## 5. Files created
Backend (`apps/whatsapp-agent`): `services/note_priority.py`, `services/required_work.py`, `services/facility_order_view.py`, `services/item_details.py`, `services/facility_issue_types.py`, `services/quote_revision.py`, `db/repositories/facility_order_reviews_repo.py`, `db/repositories/facility_quote_revisions_repo.py`, `api/internal_quote_revisions.py`.
Migrations: `20260806_000046_facility_order_experience.sql`, `..._000047_facility_issue_structured_fields.sql`, `..._000048_clarifications_quote_revisions.sql`.
Frontend (`apps/facility-dashboard`): `components/orders/PhotoViewer.tsx`, `OrderViewSections.tsx`, `GeneralPhotoLinker.tsx`, `RaiseIssueForm.tsx`, `QuoteRevisionPanel.tsx`, `lib/note-format.ts`.
Tests: `test_required_work.py`, `test_note_priority.py`, `test_facility_order_view.py`, `test_facility_order_reviews.py`, `test_item_details.py`, `test_facility_photo_linking.py`, `test_facility_issue_types.py`, `test_facility_issue_gate.py`, `test_quote_revision.py`, `test_facility_quote_revisions.py`, `test_facility_privacy_permissions.py`.
Docs/runbooks: `docs/checklists/apply-migration-000046-facility-order-experience.md`, this report, weekly report, presentation notes, spec `docs/superpowers/specs/2026-08-06-facility-order-cards-redesign-design.md`.

## 6. Files modified
Backend: `db/repositories/{facility_orders_repo,order_notes_repo,order_photos_repo,facility_issues_repo}.py`, `services/{facility_orders,order_photos}.py`, `api/{facility,facility_order_photos,internal_facility_issues}.py`, `main.py`.
Frontend facility: `app/(app)/orders/[orderId]/page.tsx`, `components/orders/{OrderCard,OrderPhotoGrid}.tsx`, `lib/api-client.ts`.
Frontend admin: `lib/dashboard/whatsapp-agent-api.ts`, `components/dashboard/operations/facility-issue-detail/FacilityIssueDetailPage.tsx`.

## 7. API endpoints added/changed
Facility: `GET /orders/{id}` (now returns structured `view`), `POST /orders/{id}/acknowledge-review`, `GET /issue-types`, `POST /orders/{id}/issues` (structured), `PATCH /orders/{id}/photos/{pid}/link`, `POST /orders/{id}/photos` (item link + issue stages), `POST /orders/{id}/quote-revision`, `GET /orders/{id}/quote-revisions`.
Internal/Ops: `POST /api/internal/facility-issues/{id}/clarification-answer`, `GET/POST /api/internal/quote-revisions[...]/review`, `/customer-decision`.

## 8. Database tables/models added/changed
New: `facility_order_reviews`, `facility_quote_revisions`. Extended: `order_notes` (priority, order_item_id, facility_issue_id), `order_photos` (order_item_id, caption, source), `orders` (facility_fee_snapshot/_total/_currency), `facility_issues` (order_item_id, requires_customer_response/photo/price_revision, photo_ids).

## 9. UI pages/components added/changed
Redesigned facility `OrderCard` + order detail; new photo viewer/lightbox, view sections, general-photo linker, raise-issue form, quote-revision panel; admin issue-detail now shows affected item, requirement chips, issue photos, revised-quote review, and clarification recording.

## 10. Agent behavior
None changed. Required Work + notes are built **deterministically** from structured data; no LLM writes work instructions or prices.

## 11. Integrations
Reuses R2/local media storage, margin rules (`facility_pricing.apply_margin`), FACILITY_SHARE_* config, order_events audit.

## 12. What is mock-only
Storage default is local; no live WhatsApp/Stripe/LLM. Customer approval of a revised price is recorded by Ops/agent (no live customer channel in MVP).

## 13. What is live
All backend logic + both dashboards against the dev/test Supabase once migrations 000046–000048 are applied.

## 14. What is intentionally deferred
Card thumbnails render a strip (not full galleries) for list performance; `facility_fee_snapshot` population at handoff is a separate wiring task; live customer-approval channel; item-level (vs order-level) pause granularity.

## 15. Tests run
Per-area targeted pytest runs + `tsc`/`eslint` on both frontends + full backend suite. See §16–17.

## 16. Test results
New backend tests (11 files, ~90 tests) all green in targeted runs. Facility + admin apps: `tsc` clean, `eslint` clean (only a pre-existing unrelated warning). Full backend suite: see weekly report for the authoritative count; the only failures are the **documented pre-existing seed-isolation race** (10 tests, unrelated to this work — confirmed by isolation reruns).

## 17. Bugs/issues found
`order_photos` has no `updated_at` (relink SQL adjusted). `_UPLOAD_EVENT` KeyError for new stages (guarded with `.get`). No product bugs surfaced.

## 18. Known limitations
See §14. Live E2E screenshots pending migration apply + stack up (`next build` unreliable on Windows here; verification is via tsc/lint/pytest per repo history).

## 19. Security/privacy notes
Every facility read is scoped by `facility_id`; the payload whitelists fields (no margin/Stripe/other-facility rates/customer amount/conversation); customer fields gated by FACILITY_SHARE_*; photos are Bearer-guarded/signed (never public URLs); facility fee never exposed to the customer path.

## 20. Cost/LLM usage notes
Zero LLM calls added.

## 21. Screens/pages to demo
Facility order list (redesigned cards), order detail (hierarchy + acknowledge gate + photo lightbox + items + revised quote), raise-issue flow; admin facility-issue detail (photos, requirement chips, revised-quote review, clarification).

## 22. Commands to run
Backend tests: `apps/whatsapp-agent` → `./.venv/Scripts/python.exe -m pytest -q`. Frontend: `apps/facility-dashboard` & `apps/admin` → `npm run typecheck && npm run lint`. Apply migrations 000046–000048 per the runbook before live use.

## 23. How to verify manually
Apply migrations; bring up Docker/Evolution/backend:8100/dashboards; open a real order in the facility app → confirm Required Work, prioritized notes, photos, items, fee, acknowledge gate; raise an issue with a photo → see it in admin; submit a revised quote → approve in admin → customer-approve → order unblocks.

## 24. Next recommended step
Wire `facility_fee_snapshot` population at facility handoff, then run a live E2E pass on the dev/test Supabase and capture demo screenshots.

## 25. Migrations to apply
`20260806_000046`, `000047`, `000048` on the dev/test Supabase (see runbook `docs/checklists/apply-migration-000046-facility-order-experience.md`; 000047/000048 headers carry their own apply/rollback).
