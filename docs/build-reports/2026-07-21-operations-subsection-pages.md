# Build Report — Operations restructured into subsection pages

**Date:** 2026-07-21
**App:** `apps/admin` · routes under `/operations/*`
**Status:** ✅ Typecheck 0 errors · isolated production build 24/24 pages · Playwright-verified (light/dark/mobile) with **0 console errors, 0 hydration errors, 0 horizontal overflow** on all Operations routes. Mock-only, UI-only.

---

## 1. Objective
The single `/operations` page had become cluttered (four heavy surfaces on one page). Restructure so each operational area is its **own clean route/page**, with `/operations` acting as a light landing page of section cards.

## 2. What changed
- `/operations` is now a **landing page**: header + four large section cards (icon, title, description, 3-KPI summary, status badge, hover state, "Open section" link). No tables/charts on the landing.
- Each area is its own route with breadcrumb + sub-nav pills (`Operations / <Section>`):
  - `/operations/customer-facing`
  - `/operations/facility-facing`
  - `/operations/drivers`
  - `/operations/customer-orders` (**new**)
- The old top **Customer Charges / Payments** tab is **removed from Operations** (payments now live as payment-status columns in Customer Orders and in Finance & Compliance). Its component file is preserved (not deleted), just no longer routed.

## 3. New Operations route structure
```
/operations                      → OperationsLanding (4 cards)
/operations/customer-facing      → CustomerFacing (existing component, moved)
/operations/facility-facing      → FacilityFacing (existing component, moved)
/operations/drivers              → Drivers (existing component, moved)
/operations/customer-orders      → CustomerOrders (new)
```
Sidebar keeps one **Operations** item → landing. `OperationsSubNav` (breadcrumb + scrollable pills) provides in-section navigation; sidebar active-state still highlights Operations on all sub-routes (`startsWith` match).

## 4. What moved from the old page
The old `/operations` rendered a segmented `Tabs` with `CustomerFacing`, `FacilityFacing`, `Drivers`, `CustomerChargesPayments`. These components were **reused as-is** (no duplication) and mounted on their own routes. Only two edits to existing components:
- **CustomerFacing:** replaced the redundant "Customer Orders" tab with a **"Conversations"** tab (orders now have a dedicated section); WhatsApp Agent console preserved as the first tab. KPI set updated to add **Refund Requests** (swapped out "New WhatsApp Orders") and relabel "Pending Customer Replies".
- Payments removed from Operations subsections (kept in Finance & Compliance).

## 5. Customer Facing page
Route `/operations/customer-facing`. 8 KPIs (Open Conversations, Pending Customer Replies, Active Tickets, Pending Cancellations, Order Change Requests, Escalated Concerns, Refund Requests, Avg Response Time). Tabs: **WhatsApp Agent** (live mock console — preserved), **Conversations** (masked, no phone column), Tickets / Concerns, Cancellations, Order Changes, Follow-ups. Global filter bar; activity + quick-actions aside. Phones masked.

## 6. Facility Facing page
Route `/operations/facility-facing`. 8 KPIs (Awaiting Assignment, In Cleaning, Delayed at Facility, Quality Check Pending, Ready for Delivery, Facility Issues Open, Top Facility, Avg Turnaround). Tabs: Facility Orders, Facility Assignment, Status Updates, Issues, Quality Checks, Delivery Handoff. **Privacy firewall banner retained** — area/city only, no customer name/phone/email/full address.

## 7. Drivers page
Route `/operations/drivers`. 10 KPIs (Active/Online drivers, Pickups/Deliveries Assigned & Completed Today, Delayed Pickups/Deliveries, Avg Pickup/Delivery Time). Tabs: Driver Overview, Pickup Queue, Delivery Queue, Driver Performance, Driver Issues. Queues show customer **area/city only**.

## 8. Customer Orders page (new)
Route `/operations/customer-orders`. Dedicated order center, distinct from support. 10 KPIs (Total Active, New, Pickup Scheduled, In Cleaning, Ready for Delivery, Out for Delivery, Completed Today, Cancelled, Orders With Issues, Payment Pending). Tabs:
- **All Orders** — Order ID, Customer, Service, Source, City/Area, Status, Pickup Slot, Facility, Driver, Amount, Payment, Actions.
- **Active Orders** — Current Status, Next Step, Facility, Driver, SLA Status.
- **Completed Orders** — Completed At, Amount, Payment, Rating.
- **Cancelled Orders**, **Orders With Issues** (Issue Type/Priority/Team/Status/Last Update), **Order Changes** (approval-gated).
Global filter bar **plus** local Order Status + Payment Status filters. Info card notes it's prepared to later read `/api/orders/*` (not wired). Reads the shared `orders` mock.

## 9. Files created
- `app/(dashboard)/operations/customer-facing/page.tsx`
- `app/(dashboard)/operations/facility-facing/page.tsx`
- `app/(dashboard)/operations/drivers/page.tsx`
- `app/(dashboard)/operations/customer-orders/page.tsx`
- `components/dashboard/operations/OperationsLanding.tsx`
- `components/dashboard/operations/OperationsSubNav.tsx`
- `components/dashboard/operations/CustomerOrders.tsx`
- `docs/build-reports/2026-07-21-operations-subsection-pages.md` (this)

## 10. Files modified
- `app/(dashboard)/operations/page.tsx` — now the landing (was the 4-tab page).
- `components/dashboard/operations/CustomerFacing.tsx` — Conversations tab replaces Customer Orders tab.
- `lib/dashboard/operations-data.ts` — `customerFacingKpis` updated (+ Refund Requests); added Customer Orders data (`customerOrdersKpis`, `nextStepByStatus`, `orderSla`, `orderRatings`, `orderIssues`, `orderCenterActivity`, tone maps).
- `lib/dashboard/formatters.ts` — `formatRelativeTime` now computes against a fixed `MOCK_NOW` (2026-07-20T10:00Z) instead of real `Date.now()`. **Fixes a repo-wide React #425 hydration text mismatch** on statically-prerendered pages (server-built relative strings vs later client hydration) and makes the demo deterministic.
- `next.config.js` — `distDir` is now `process.env.LK_DIST_DIR || ".next"` so an isolated build/verify never collides with a running `next dev` (see Testing).
- Docs: architecture, checklist, 00-Home updated.

## 11. Filter behavior
- Customer Facing / Facility Facing / Drivers: existing **global** filter bar (date/market/city/channel/service where applicable) via the existing `filter*` predicates — unchanged.
- Customer Orders: global filter bar **+ local** Order Status & Payment Status (`LocalFilterBar`). Global order filtering via `filterOrders`; local via `matchesLocal`.
- No broken/irrelevant filters left on any subsection.

## 12. Privacy safeguards
- Facility Facing: privacy firewall banner + area/city-only tables (unchanged).
- Drivers: area/city only in queues.
- Customer Facing: phones masked; Conversations table has **no phone column**.
- Customer Orders: shows customer name in the order center (operational need) but no phone/email/full address; payment shown as status only (no card/bank data).

## 13. Tests / checks run (honest)
- `npx tsc --noEmit` → **0 errors**.
- `npx next lint` → clean (1 pre-existing unrelated warning in `app/admin/conversations`).
- Production build: `npx next build` fails on this repo's **known Windows `.next` rename/trace race** — *and* the dev server on `:3005` owns the shared `.next`. Worked around by building to an **isolated `distDir`** (`LK_DIST_DIR=.next-verify`): **build exit 0, 24/24 static pages**.
- Runtime smoke (isolated prod `next start`): all 5 Operations routes + all other sections → **200**.
- Playwright (light + dark @1280; mobile @390): all Operations routes → **0 console errors, 0 hydration (#425) errors, 0 horizontal overflow**; landmarks verified (4 landing cards, WhatsApp Agent tab present, Facility privacy banner present, mobile desktop-table collapses to cards).
- Verified the user's live dev server (`:3005`) recovered and serves healthy CSS after the isolated verification.

## 14. Known limitations
- Customer Orders is mock (reads the shared `orders` mock); prepared but **not wired** to `/api/orders/*`.
- `CustomerChargesPayments.tsx` remains in the tree unused (preserved per the migration rule).
- Local filters reset on reload (consistent with the global filter store).
- Windows `next build` still can't write the shared `.next` while `next dev` runs — build/verify via `LK_DIST_DIR` or with the dev server stopped.

## 15. Recommended next step
Wire Customer Orders (read-only) to the WhatsApp agent order APIs (`/api/orders/active|completed|metrics`) behind the mock flag, then add URL-synced filters so a filtered order view is shareable.
