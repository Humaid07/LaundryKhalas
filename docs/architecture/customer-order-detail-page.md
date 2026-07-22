# Customer Order Detail Page

Status: **Active** · Last updated: 2026-07-22

The Customer Orders subsection opens each order card as a **dedicated full-page
order workspace**, not a right-side drawer. This is a deliberate exception to the
shared Operations drawer pattern (see [[operations-navigation]]): an order record
is information-dense — lifecycle, itemised services, customer, payment, facility &
driver assignment, notes, the linked conversation and an audit feed — so it earns
a spacious, scannable page instead of a cramped 480px slide-over.

## Route

```
/operations/customer-orders/[orderId]
```

- **Server component** (`app/(dashboard)/operations/customer-orders/[orderId]/page.tsx`).
  Reads `orderId` and the active status tab from the route — no client search-param
  hook, no Suspense boundary needed.
- The list carries the active tab into the card link as `?tab=<tabId>`; the detail
  page reflects it back into the **breadcrumb / back** target
  (`/operations/customer-orders?tab=<tabId>`) so returning lands on the exact view
  the operator came from. Global dashboard filters persist via `FiltersProvider`.
- Unknown `orderId` → a clean "Order not found" state with a back button (no broken
  layout).

## Page structure

```
OrderHeader          breadcrumb · back · id + status/service/priority badges ·
                     grouped actions (Change status / Assign driver / Assign
                     facility / Reschedule) + "More actions" overflow
OrderSummaryStrip    scannable pill row: customer · service · pickup · delivery ·
                     payment · method · amount · driver · facility · source
────────────────────────────────────────────────────────────────────────────
MAIN COLUMN (2/3)                         SIDEBAR (1/3, sticky)
  Order overview                            Customer snapshot (masked phone +
  Items & service breakdown                   role-gated reveal)
  Pickup & delivery                         Payment snapshot
  Order lifecycle (timeline)                Assignment (facility / driver / QC)
  Internal notes (add + list)               SLA & next step
  Related conversation                      Quick actions
  Order events (audit feed)
```

On < `lg` the two columns collapse into a single stacked column (mobile/tablet
usable); the summary strip reflows from 5 → 3 → 2 pills per row.

## Components

All new, under `apps/admin/components/dashboard/operations/order-detail/`:

| File                          | Responsibility                                         |
| ----------------------------- | ------------------------------------------------------ |
| `CustomerOrderDetailPage.tsx` | Page shell — composes header, strip, 2-column grid, sticky sidebar (`SlaCard`, `QuickActionsCard` live here) |
| `OrderHeader.tsx`             | Breadcrumb, back, identity + badges, grouped action buttons + `ActionMenu` overflow |
| `OrderSummaryStrip.tsx`       | The at-a-glance pill row                                |
| `OrderLifecycleTimeline.tsx`  | Premium step-based vertical timeline (done / current / future), with cancelled & concern banners |
| `OrderItemsTable.tsx`         | Itemised service breakdown (no invented per-line prices) |
| `cards.tsx`                   | Overview · Pickup/Delivery · Customer · Payment · Assignment · Internal notes · Related conversation · Order events |
| `primitives.tsx`              | `SectionCard`, `Field`/`FieldGrid`, `Chip`, `ActionMenu` |
| `data.ts`                     | Pure, deterministic derivations from the mock order     |

The detail page reuses the same `orders` mock (`lib/dashboard/mock-data.ts`) the
list reads, plus operations context (`operations-data.ts`) for SLA, next-step,
QC and issues — no new data source.

## Lifecycle timeline — deterministic step times

`data.ts::stepTime(order, index)` anchors each reached step **between the order's
`createdAt` and `MOCK_NOW`**: step 0 lands on `createdAt`, the current step on
~now, intermediate steps spread across that span. Consequences:

- A **completed** step is always in the **past** — it never renders a future
  "in X" timestamp (the earlier naive `createdAt + index·42min` derivation drifted
  completed steps past `MOCK_NOW`).
- No `Date.now()` / `Math.random()` — server render and client hydration produce
  identical strings (avoids React #425 hydration mismatch), consistent with the
  repo-wide `MOCK_NOW` convention in `lib/dashboard/formatters.ts`.
- **Cancelled** / **Concern Raised** orders (not on the linear ladder) show a
  banner and a fully-muted ladder instead of a misleading progress bar.

## Actions (mock-only)

Actions are embedded in the page, never floating:

- **Header**: Change status · Assign driver · Assign facility · Reschedule, plus a
  "More actions" overflow holding Add note · Open conversation · Escalate · Mark
  ready · Mark delivered · **Cancel order** (disabled once Delivered/Cancelled) ·
  **Request refund review** (`Approval` chip).
- **Sidebar Quick actions**: the common operational verbs.
- Only real navigations act (back, Open conversation → `/operations/customer-facing?
  conversationId=…&orderId=…`). Everything else is visual in mock mode. Refunds,
  cancellations outside policy and outbound replies remain **approval-gated**
  (CLAUDE.md §6/§13). Nothing is dispatched live.

## Privacy

- Customer **phone is masked** by default; a role-gated **"Reveal phone"** toggle
  exposes the full number and shows an access-logged notice.
- Full pickup/delivery **address is role-gated** — the page states this rather than
  printing it; customer contact is routed through the WhatsApp conversation only.
- Internal notes and AI reasoning are explicitly kept out of customer- and
  facility-facing surfaces (privacy firewall, CLAUDE.md §7).

## Reusability

`SectionCard` / `Field` / `FieldGrid` / `Chip` / `ActionMenu` and the header +
timeline patterns are intentionally generic, so the same detail-page shape can be
adapted later for **facility-facing order detail**, **driver task detail**,
**ticket detail** and **conversation detail**.

See also: [[operations-navigation]] · [[mock-order-lifecycle]] · [[privacy-firewall]] ·
[[dashboard-information-architecture]]
