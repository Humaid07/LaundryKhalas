# Build Report — Customer Order Detail Redesign (drawer → full page)

**Date:** 2026-07-22
**Branch:** `seo-agent-foundation`
**Area:** Admin dashboard · Operations · Customer Orders

## 1. Objective

Replace the cramped right-side detail **drawer** for Customer Orders with a
**dedicated full-page order workspace** at `/operations/customer-orders/[orderId]`
— cleaner, more spacious, more premium, and operationally useful.

## 2. What was built

A full-page order detail experience that opens when a Customer Order card is
clicked, with:

- **Header**: breadcrumb (Operations › Customer Orders › Order LK-…), back button,
  order id + status/service/priority badges, grouped primary actions and a
  "More actions" overflow menu.
- **Summary strip**: a scannable pill row (customer, service, pickup, delivery,
  payment, method, amount, driver, facility, source).
- **Two-column body** (2/3 main + sticky 1/3 sidebar) covering every required
  section: overview, items breakdown, pickup & delivery, lifecycle timeline,
  internal notes, related conversation, order events; sidebar = customer snapshot,
  payment snapshot, assignment, SLA/next-step, quick actions.
- A **premium step-based lifecycle timeline** (done / current / future) with
  cancelled & concern banners.
- Full **responsive** collapse to a single column on tablet/mobile.

## 3. Why

The drawer felt cramped, hard to read and could not present a dense order record
well. An order carries lifecycle + items + customer + payment + assignment + notes
+ conversation + audit history — that earns a spacious page, not a 480px slide-over.

## 4. Old behavior vs new behavior

| | Old | New |
| --- | --- | --- |
| Open an order card | 480px right-side **drawer** overlay | **Full page** `/operations/customer-orders/[orderId]` |
| Space | Cramped, single narrow column | Header + strip + 2-column workspace |
| Lifecycle | Plain dot list; completed steps could show **future** times | Step-based timeline; completed steps always in the **past**, current = "just now" |
| Back | Close overlay | Back/breadcrumb → list, **active status tab preserved** via `?tab=` |
| Actions | Drawer footer only | Header buttons + overflow + sidebar quick actions |

The drawer primitives (`DetailDrawer`, `DrawerActions`) are **retained unchanged**
for Customer Facing / Facility Facing / Drivers — only Customer Orders moved to the
full-page pattern.

## 5. Route changes

- Added `app/(dashboard)/operations/customer-orders/[orderId]/page.tsx`
  (server component; reads `orderId` + `?tab=`; "Order not found" fallback).
- `CustomerOrders.tsx` navigates via `router.push('/operations/customer-orders/${id}?tab=${tab}')`
  instead of opening a drawer.

## 6. Files

**Added** (`apps/admin/components/dashboard/operations/order-detail/`):
`CustomerOrderDetailPage.tsx`, `OrderHeader.tsx`, `OrderSummaryStrip.tsx`,
`OrderLifecycleTimeline.tsx`, `OrderItemsTable.tsx`, `cards.tsx`, `primitives.tsx`,
`data.ts`; and route `.../customer-orders/[orderId]/page.tsx`.

**Modified this task:**
- `order-detail/data.ts` — fixed lifecycle/event time derivation: `stepTime` now
  anchors between `createdAt` and `MOCK_NOW` (imported from `formatters`) so
  completed steps are never shown as future timestamps.

**Docs:** added `docs/architecture/customer-order-detail-page.md`; updated
`docs/architecture/operations-navigation.md` (Customer Orders = full-page
exception) and `docs/00-Home.md`.

## 7. API / DB

None. Reuses the existing `orders` mock (`lib/dashboard/mock-data.ts`) and
`operations-data.ts` helpers. No backend, schema or migration changes.

## 8. UI pages/components

See §6. All new components use shared design tokens (`SectionCard`, `Field`,
`Chip`, `StatusBadge`, `Button`) — rose/white system, soft borders, spacious
padding, sticky sidebar.

## 9. Agent behavior

None changed. This is admin UI only.

## 10. UX improvements

- Full-page, spacious, premium layout with clear hierarchy (header → strip →
  sections).
- Elegant vertical lifecycle timeline with a highlighted "Current" step and muted
  future steps.
- Back navigation preserves the exact status tab.
- Graceful handling of cancelled / flagged / unassigned / not-found orders.

## 11. Actions moved into detail page

Change status · Assign driver · Assign facility · Reschedule · Add internal note ·
Open customer conversation · Escalate to human · Mark ready for delivery · Mark
delivered · Cancel order (disabled when Delivered/Cancelled) · Request refund
review (`Approval`-chipped). All mock-only except real navigations; refunds /
cancellations stay approval-gated.

## 12. What is mock-only / live / deferred

- **Mock-only:** all order data and every action except back / open-conversation
  navigation.
- **Live:** nothing. No live WhatsApp, Stripe, LLM or external calls.
- **Deferred:** wiring actions to real state/endpoints; applying the same
  full-page detail pattern to facility / driver / ticket / conversation records.

## 13. Tests run & results

- `npx tsc --noEmit` (apps/admin) → **clean, 0 errors**.
- `npx tsx lib/dashboard/filters.test.ts` → **45/45 assertions passed**.
- **Playwright** (headless Chromium, dev server :3007):
  - Click order card → navigates to `/operations/customer-orders/LK-24817?tab=all`.
  - `[role="dialog"]` count = **0** (no drawer).
  - Breadcrumb, summary strip, lifecycle, all sections present.
  - Back link href preserves the active tab (`?tab=issues`).
  - Lifecycle text: completed steps read "48 secs ago … 8 secs ago", current =
    "just now", future step undated — **no future "in X" on completed steps**.
  - Verified desktop (1440), flagged order (LK-24812), and mobile (390px stack).

## 14. Bugs found & fixed

- **Completed lifecycle steps rendered future timestamps.** The original
  `stepTime` = `createdAt + index·42min` drifted later steps past `MOCK_NOW`, so a
  done step showed "in 3 mins". Fixed by anchoring step times between `createdAt`
  and `MOCK_NOW`.

## 15. Known limitations

- Actions are visual only (mock mode) — no persistence/endpoints yet.
- Relative-time strings use the shared repo-wide `formatRelativeTime`, whose unit
  labels are one tier coarse (e.g. 48 min reads "48 secs"). This is a **pre-existing,
  app-wide** convention (18 call sites, no test pins it) and was intentionally left
  untouched to keep the timeline consistent with every other timestamp in the
  dashboard; changing it is a separate, global task.
- Full address and unmasked phone are role-gated placeholders (no real RBAC yet —
  RBAC/auth remains the outstanding P0 for the dashboard overall).

## 16. Security / privacy notes

Phone masked by default with a logged reveal; full address role-gated and not
printed; internal notes/AI reasoning excluded from customer/facility surfaces;
refunds & out-of-policy cancellations approval-gated. Consistent with CLAUDE.md
§6/§7/§13.

## 17. Cost / LLM usage

None — no LLM calls.

## 18. Screens to demo

1. Customer Orders list → click a card → full-page detail opens.
2. Lifecycle timeline (done/current/future) on an in-progress order (LK-24817).
3. Flagged order (LK-24812) — concern banner, "At risk" SLA, linked escalation.
4. Mobile single-column stack.
5. Back button returns to the same status tab.

## 19. Commands to run

```bash
cd apps/admin
npm run dev          # http://localhost:3000
npx tsc --noEmit
npx tsx lib/dashboard/filters.test.ts
# open /operations/customer-orders and click any card
```

## 20. How to verify manually

Open `/operations/customer-orders`, switch a status tab, click a card → confirm a
full page (not a drawer) with breadcrumb + summary strip + timeline; click Back →
confirm you return to the same tab.

## 21. Next recommended step

Wire the header/quick actions to real state transitions and the approval queue, then
generalise the detail-page pattern to facility-facing / driver / ticket records.
