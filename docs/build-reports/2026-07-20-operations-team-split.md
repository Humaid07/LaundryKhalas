# Build Report — Operations split into Customer Facing & Facility Facing

**Date:** 2026-07-20
**App:** `apps/admin` · route `/operations`
**Status:** ✅ Built, typechecked, built, browser-verified (light/dark/mobile). Mock-only, UI-only.

---

## 1. Objective
Stop treating Operations as one mixed area. Split it into **two teams** with
clearly separated surfaces:
1. **Customer Facing** — the team handling customers directly.
2. **Facility Facing** — the team running cleaning facilities and handoff.

## 2. Why it was split
Customer-side and facility-side work have different jobs, different data, and —
critically — **different privacy needs**. A facility operator should never see a
customer's phone, email or full address; a customer-support agent needs customer
context. One mixed table couldn't serve both safely or clearly. Splitting gives
each team its own KPIs, tables, actions and activity feed, and lets the facility
side enforce the privacy firewall by construction.

## 3. New structure
`/operations` now has a **segmented top-level switch**: `Customer Facing` |
`Facility Facing`. Each team has a KPI row, a global filter bar, secondary
(underline) tabs for its tables/lists, an activity timeline, and a quick-actions
side panel.

**Customer Facing** secondary tabs: WhatsApp Agent (the live agent console) ·
Customer Orders · Tickets / Concerns · Order Changes · Cancellations · Follow-ups.

**Facility Facing** secondary tabs: Facility Orders · Facility Assignment
(+ Facility Management table) · Status Updates · Issues · Quality Checks ·
Delivery Handoff.

## 4. KPIs (distinct per team)
- **Customer:** Open Conversations, Pending Replies, New WhatsApp Orders, Active
  Tickets, Pending Cancellations, Order Change Requests, Escalated Concerns, Avg
  Response Time.
- **Facility:** Awaiting Assignment, In Cleaning, Delayed at Facility, Quality
  Check Pending, Ready for Delivery, Facility Issues Open, Top Facility, Avg
  Turnaround.

## 5. Privacy differences (the important part)
- **Facility-facing views carry NO customer PII.** Facility Orders, Quality
  Checks and Delivery Handoff show **area/city only** (e.g. "Dubai · Dubai
  Marina") — no customer name, phone, email, full address, or complaint notes. A
  persistent "Privacy firewall on" banner states this on the Facility tab.
  Verified programmatically: **0 phone-like strings** appear anywhere in the
  Facility Facing view.
- **Customer-facing views** may show customer support context, but phone numbers
  are still **masked** (`maskPhone`, e.g. `+9715 •••• 71`).

## 6. Pages / components changed
- **New:** `lib/dashboard/operations-data.ts` (types + mock data for both teams),
  `components/dashboard/operations/CustomerFacing.tsx`,
  `components/dashboard/operations/FacilityFacing.tsx`.
- **Rewritten:** `app/(dashboard)/operations/page.tsx` — now just the two-team
  segmented Tabs. (Old single-level tabs — WhatsApp/Orders/Tickets/Driver/Changes
  — are superseded; the live WhatsApp console moved under Customer Facing.)
- **Extended:** `components/dashboard/ui/Tabs.tsx` — added a `segmented` variant
  for the top-level team switch (so the nested underline tabs read as a sub-level).
- **Extended:** `components/dashboard/widgets.tsx` — `ActivityTimeline` now accepts
  events with an optional `actor`.
- **Fixed:** `components/dashboard/ui/DataTable.tsx` — dropped an unused
  `T extends { id?: string }` constraint that blocked the id-less `Facility` type.

## 7. Mock data added (LaundryKhalas-specific)
- **Customer:** cancellations, order-change requests, customer follow-ups,
  customer activity feed, customer KPIs.
- **Facility:** 6 facilities (capacity/load/PPI/delayed/status), facility order
  queue (area-only), facility issues, quality checks, delivery handoff, facility
  activity feed, facility KPIs. Examples cover: assigned to Al Quoz, in cleaning,
  quality-check pending, West Bay over-capacity delay, ready for delivery,
  awaiting-assignment/reassignment.

## 8. Tests / checks run
- `tsc --noEmit`: **PASS** (0 errors, after the DataTable fix).
- `npm run build`: **PASS** — `/operations` compiles (17.9 kB).
- **Playwright** (light + dark + mobile): both top tabs present; distinct KPIs per
  team; Facility privacy banner + Area column present; **0 phone-like strings in
  Facility view**; **0 console errors** in all three viewports. Screenshots taken.

## 9. Known limitations
- All actions are non-persisting placeholders (mock).
- Filters remain presentational (don't re-slice data yet).
- The WhatsApp console is still a single live "test customer" session.

## 10. Next recommended step
Wire facility actions (assign/reassign/status/quality) to a mock store so state
changes persist within a session, and make the global filters actually filter.
