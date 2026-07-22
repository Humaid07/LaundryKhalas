# Build Report — Operations Workflow Tabs Refactor

**Date:** 2026-07-22
**Branch:** `seo-agent-foundation`
**Area:** Admin dashboard → Operations

## 1. Task objective

Fix Operations page-level tabs. The four Operations **subsections** (Customer
Facing, Facility Facing, Drivers, Customer Orders) must live **only in the left
sidebar**. The **top tabs inside each subsection** must show that page's
**workflow / status views** — not links to other subsections. Cards must be
clickable and open a detail drawer; all actions must live inside that drawer;
the standalone generic "Order Actions" / action panels must be removed.

## 2. What was built / changed

- Migrated the two remaining old-pattern subsections — **Customer Facing** and
  **Drivers** — onto the shared Operations workspace pattern
  (`WorkflowTabs → CardGrid/RecordCard → DetailDrawer` with actions inside).
  (Facility Facing and Customer Orders were already on this pattern.)
- Replaced each page's top tabs with the **required workflow/status tab set**.
- Removed the standalone **Driver actions** and **Customer actions** panels; all
  record actions now live only inside the detail drawer for the selected record.
- Kept the **WhatsApp Inbox** tab rendering the full interactive `WhatsAppInbox`
  (thread + composer) on Customer Facing; every other tab is a clickable card
  grid → drawer.
- Deleted dead `OperationsSubNav.tsx` (a leftover subsection tab strip, no longer
  imported anywhere).
- Removed the residual "Mock mode" wording from the two migrated drawers' action
  notes (honours the owner "no mock/demo words in UI" rule).
- Documented the rule in `docs/architecture/operations-navigation.md`.

### Required tab sets (now live)

- **Customer Facing:** WhatsApp Inbox · Pending Replies · Human Takeover · Tickets ·
  Cancellations · Follow-ups · Complaints · Escalations
- **Facility Facing:** All Facility Orders · Awaiting Assignment · In Cleaning ·
  Quality Check · Delayed at Facility · Ready for Delivery · Facility Issues · Handoffs
- **Drivers:** Driver Overview · Pickup Queue · Pickup Scheduled · In Transit to
  Facility · Delivery Queue · Out for Delivery · Completed Deliveries · Driver Issues
- **Customer Orders:** All Orders · New Orders · Active Orders · Pickup Scheduled ·
  In Cleaning · Ready for Delivery · Out for Delivery · Completed · Cancelled ·
  Issues / Escalations

## 3. Files

**Modified**
- `apps/admin/components/dashboard/operations/CustomerFacing.tsx` — full rewrite to workspace pattern + new tab set.
- `apps/admin/components/dashboard/operations/Drivers.tsx` — full rewrite to workspace pattern + new tab set.
- `apps/admin/components/dashboard/operations/FacilityFacing.tsx` — action-note wording.
- `apps/admin/components/dashboard/operations/CustomerOrders.tsx` — action-note wording + removed unused import.

**Deleted**
- `apps/admin/components/dashboard/operations/OperationsSubNav.tsx` — dead subsection tab strip.

**Added**
- `docs/architecture/operations-navigation.md` — the Operations navigation rule.
- `docs/build-reports/2026-07-22-operations-workflow-tabs-refactor.md` — this report.

## 4. Data / routes

- No new data models, migrations or API endpoints. Tabs are deterministic
  status/category filters over existing mock data
  (`conversations`, `tickets`, `cancellations`, `customerFollowups`,
  `pickupQueue`, `deliveryQueue`, `drivers`, `driverIssues`).
- Route structure unchanged: `/operations/{customer-facing,facility-facing,drivers,customer-orders}`.

## 5. Derivation notes (mock, no invented data)

- Drivers: `Pickup Scheduled` = assigned/awaiting pickups; `In Transit to Facility`
  = `Picked Up`; `Out for Delivery` = en-route/assigned deliveries;
  `Completed Deliveries` = `Delivered`.
- Customer Facing: `Complaints` = tickets in {Damage, Quality, Lost Item};
  `Escalations` = unresolved `Urgent` tickets; `Pending Replies` / `Human Takeover`
  = conversation status filters.

## 6. Mock-only / live / deferred

- **Mock-only:** all Operations data and every drawer action (no live dispatch).
- **Live:** none.
- **Deferred:** wiring drawer actions to real backend mutations.

## 7. Tests / verification

- `npx tsc --noEmit` → **0 errors** (whole admin app).
- Playwright (dev server :3005), all pass:
  - All four pages show their required workflow tabs; **none** shows Customer
    Facing / Facility Facing / Drivers / Customer Orders as tabs.
  - Cards clickable → detail drawer opens on Customer Orders, Drivers (Pickup
    Queue), Customer Facing (Pending Replies).
  - Drawer footer carries the record's actions (Change status, Assign facility/
    driver, Reschedule, Escalate, Cancel, Refund-with-Approval, etc.).
  - No standalone "Driver actions" panel remains on the page body.

## 8. Known limitations

- `orderChanges` / `customerActivity` mock arrays are now unused by Customer Facing
  (kept in `operations-data.ts` for possible reuse; harmless).
- Actions are visual only in mock mode.

## 9. Privacy / security notes

- Facility & Driver views: area/city only, no customer PII.
- Customer Facing & Customer Orders: masked phones in lists; role-gated full detail.
- Refunds / out-of-policy cancellations / outbound replies are approval-gated.

## 10. Next recommended step

Wire the highest-value drawer actions (Change status, Assign driver/facility,
Approve cancellation) to the live orders API behind the existing feature flag.
