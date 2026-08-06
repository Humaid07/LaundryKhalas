# Facility Order Cards & Detail — Redesign + Backend Integration

**Date:** 2026-08-06
**Status:** Approved for sequential ("Everything, sequential") build with check-ins between areas.
**Owner:** dev@laundrykhalas.com

---

## 1. Objective

Every Facility Dashboard order card and detail view must let a facility user immediately understand:
what the order contains, what work must be done, which notes/photos matter, and what action to take
next — **without** opening multiple pages, reading raw JSON, or reading the WhatsApp conversation.

## 2. Ground truth (what already exists — reuse, do not rebuild)

**Frontend** (`apps/facility-dashboard`, Next.js 15 + custom rose design system, port 3010):
- `components/orders/OrderCard.tsx`, `app/(app)/orders/page.tsx` (list), `app/(app)/orders/[orderId]/page.tsx` (detail).
- `components/orders/OrderPhotos*` — R2-backed, Bearer-guarded blob thumbnails, uploader, signed URLs.
- Design system: `components/ui/Button.tsx`, `components/ui/primitives.tsx` (`StatusBadge`, `Panel`),
  `components/ui/tones.ts`, `components/minimal/DetailSectionCard.tsx` / `DetailPageShell.tsx`,
  `components/ui/states.tsx`. Icons: `lucide-react`. `cn` in `lib/utils.ts`.
- API client: `lib/api-client.ts` (`facilityApi.*`, base `NEXT_PUBLIC_FACILITY_API_URL ?? http://localhost:8100`),
  `normalizeOrder()`, permissive DTOs. Auth: `lib/auth-context.tsx`, `lib/roles.ts` (`canManageFacility`).

**Backend** (`apps/whatsapp-agent`, FastAPI :8100; `DATABASE_MODE=supabase` real, `sqlite` for hermetic tests):
- Orders: `orders` table; items stored as JSON (`items`, `line_items`) — **no `order_items` table**.
- `order_notes` table (mig 000033) — categories: `PICKUP_INSTRUCTION, DELIVERY_INSTRUCTION, ACCESS_INSTRUCTION,
  CONTACT_PREFERENCE, TIMING_PREFERENCE, ITEM_HANDLING, STAIN_NOTE, EXISTING_DAMAGE, SPECIAL_CARE,
  FACILITY_INSTRUCTION, INSPECTION_REQUIREMENT, OTHER_OPERATIONAL_NOTE`. Repo `order_notes_repo.py`,
  policy `services/order_notes.py` (`group_active_by_category`, `build_confirmed_snapshot`).
- `order_photos` unified media table (mig 000032/000034) — R2 + local, signed URLs, stages
  (`intake, pre_dispatch` live; `customer_reference, damage_report, issue_photo, ...` reserved).
  Repo `order_photos_repo.py`; service `services/order_photos.py` + `services/media_storage.py`.
- `facility_issues` + `facility_issue_messages` (mig 000018) — status enum includes `acknowledged`;
  repos + Ops router `api/internal_facility_issues.py` + facility router `api/facility.py /issues*`.
- `pending_tasks` (mig 000024) — `facility_quote_status(order)` derives `pending|received|none`.
- `facility_rates` / `margin_rules` (mig 000027) — internal only; `services/facility_cost.py`
  → `FacilityCostResult.to_snapshot()` (computed, **not persisted per order**).
- `FACILITY_SHARE_*` flags (`settings.py:334`) consumed by `services/facility_handoff.py`
  (`build_facility_handoff_payload` — the PII-safe facility serializer to extend).
- Facility-scoped repo `db/repositories/facility_orders_repo.py` (`to_facility_read`, every query
  filters `o.facility_id = $1`); scope dep `api/deps.require_facility_scope`.
- Status vocabulary: `services/order_store.py:31` (`draft, active, pickup_scheduled, picked_up,
  in_cleaning, ready_for_delivery, out_for_delivery, completed, cancelled, abandoned, support_required,
  cancellation_requested, pickup_change_requested`); trigger `trg_orders_status_transition` (mig 000029).
- Latest migration: **000045**. Next: **000046**.

**Test harness:** `apps/whatsapp-agent/tests/` (pytest, `asyncio_mode=auto`). Hermetic SQLite; facility
asyncpg paths tested by monkeypatching `db.database.fetch/fetchrow` and asserting SQL + pure functions.
Frontend: `tsc` + `eslint` (no component test runner today).

## 3. Design principles

- **Reuse first.** Extend `to_facility_read` / `facility_handoff` rather than new serializers where possible.
  Reuse every existing UI primitive; no new design language.
- **Deterministic Required Work.** Built from structured `line_items`/`items` + `order_notes` +
  alteration/measurement data. If an LLM sentence is ever used it must be validated against structured
  data. Never surface an invented work instruction.
- **Privacy firewall.** Honor `FACILITY_SHARE_*`; never expose margin/Stripe/other-facility rates,
  full WhatsApp conversation, or unrelated customer data. Backend re-enforces on every read/write.
- **Backend-authoritative.** Frontend state never changes order status; all actions validated server-side.
- **Additive, idempotent migrations.** Facility isolation via app-level `facility_id` filtering.

## 4. Canonical facility-order payload

Single serializer returns (fields gated by share config; internal fields never included):

```
{ order: {id, order_number, status, status_label, priority, service_summary,
          required_work_summary[], pickup_window{start,end}, expected_completion_at,
          time_remaining, item_count, currency},
  items: [ {id, name, category, quantity, service, service_subtype, instruction,
            measurements, colour, brand_candidate, luxury_flag, stains, existing_damage,
            special_handling, photo_count, inspection_required, facility_fee, turnaround,
            item_status, wash_fold?, dimension?} ],
  notes: { <category>: [ {id, category, priority, text, item_id, source, source_message_id,
            customer_confirmed, is_amendment, created_at, updated_at} ], amendments: [...] },
  photos: [ {id, item_id, source, media_type, caption, uploaded_by, created_at, stage,
             thumb_url, view_url} ],
  customer: { name?, phone_masked?/phone?, ... },   # share-config gated
  location: { typed_address?, building?, ..., pin? , map_preview? },   # share-config gated
  facility_finance: { fee_total, per_item[], currency, payout_status },   # NO margin/stripe
  issues: [ ... ], available_actions: [ ... ],
  review_acknowledgement: { acknowledged_at?, order_version, notes_version, photo_version,
                            invalidated_at?, invalidation_reason?, up_to_date: bool } }
```

## 5. Decomposition — sequential areas (check-in between each)

**Area 1 — Backend foundation.** Migration 000046: `order_notes.priority`
(`NORMAL|IMPORTANT|CRITICAL`, default NORMAL); `order_photos.order_item_id uuid null`, `.caption text`,
`.source text`; `orders` fee-snapshot cols (`facility_fee_snapshot jsonb`, `facility_fee_total numeric`,
`facility_fee_currency text`) + version counters (`order_version int`, `notes_version int`,
`photo_version int`); new `facility_order_reviews` table. New pure `services/required_work.py`
(deterministic builder). New `services/facility_order_view.py` serializer assembling the payload from
existing repos (extends `facility_handoff` patterns). Backend tests (pure + SQL-shape).

**Area 2 — Card + detail redesign.** New `GET /api/facility/orders/{id}/view` (or extend
`/orders/{id}`). Redesign `OrderCard` preview (header+status, Required Work summary, critical notes,
photo thumbs, item count, pickup window, expected completion, fee, next action). Redesign detail view
to the 9-section hierarchy. Photos on card. `tsc`+`eslint`.

**Area 3 — Review-acknowledgement.** `POST /orders/{id}/acknowledge-review` (stores facility_user_id,
facility_id, order_version, notes_version, photo_version, acknowledged_at). Gate "Start Processing"
behind up-to-date ack. Invalidate on new CRITICAL note / new photo / amendment. Idempotent. Tests.

**Area 4 — Item-level details + per-item media linking.** Render each item (service, subtype,
instruction, measurements, colour, brand, luxury, stains, damage, special handling, photo count,
inspection, fee, turnaround, status). Wash&Fold (bags/weight/tier), carpet/curtain (est vs confirmed
sqm, rate, min charge), shoe/bag/leather (category, brand, material, inspection, quote). Link photos to
items; "General Order Photos" for unmatched; Ops/authorized-facility relink. Tests.

**Area 5 — Raise-issue redesign + Ops integration.** Issue create (category from full enum + explanation
+ photo attach → `issue_photo` stage). Surface in Ops dashboard (`apps/admin`), pause affected stage,
notify Ops, audit. Tests.

**Area 6 — Clarification + revised-quote workflows.** Clarification → Ops → amendment linked to item,
shown as "new" until acknowledged, audit-preserving. Revised quote → item `PRICE_REVISION_REQUIRED` →
Ops review → backend margin calc → customer approval gate. No auto price change, no facility/margin leak
to customer. Tests.

**Area 7 — Privacy, permissions, finance visibility, audit events.** Verify Facility A cannot read
Facility B; finance shows fee+payout only (no margin/Stripe/other rates); share-config field omission;
secure media access + expired-signed-URL rejection; structured audit events (`facility_order_viewed`,
`facility_order_details_acknowledged`, `facility_order_review_invalidated`, `facility_issue_created`, …);
immutable per-order fee snapshot (no recalculation from updated rate card). Tests.

**Area 8 — Responsive/accessibility + full sweep + docs.** Desktop/tablet/mobile; keyboard nav;
alt/captions; confirmation dialogs for destructive actions; full backend + frontend sweep; build report +
weekly report + presentation notes + 00-Home links per CLAUDE.md §11–13.

## 6. Testing strategy

Backend: pure-function unit tests (required_work, serializer shaping, invalidation logic) + SQL-shape
tests (monkeypatch `db.database`) matching existing facility test pattern. Frontend: `tsc --noEmit` +
`eslint`; component render assertions where a runner exists, else typed-serializer contract tests.
Each area: run the full `apps/whatsapp-agent` suite; fix regressions before check-in.

## 7. Non-goals / guardrails

No live WhatsApp/Stripe/LLM. No auto customer-price change. No margin/Stripe/other-facility exposure.
No separate/standalone dashboard. No new design language. Migrations applied to dev/test Supabase per
existing runbook (documented, not auto-run in CI).
