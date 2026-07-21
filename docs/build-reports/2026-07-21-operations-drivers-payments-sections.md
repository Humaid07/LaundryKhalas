# Build Report — Operations: Drivers + Customer Charges / Payments sections

**Date:** 2026-07-21
**App:** `apps/admin` · route `/operations`
**Status:** ✅ Built, typechecked (0 errors), production build passed, browser-verified (light/dark/mobile, no horizontal overflow, no new console errors). Mock-only, UI-only.

---

## 1. Objective
Expand the Operations page from **2** top-level surfaces to **4**, so the ops team can manage
the full order lifecycle end to end:

1. Customer-side conversations/orders/tickets (existing)
2. Facility-side cleaning/handoff workflows (existing)
3. **Driver-side pickup/delivery workflows (new)**
4. **Customer charges, payment status, refunds, adjustments, pending payments (new)**

## 2. What was built
Two new **top-level** Operations segmented tabs — equal siblings of Customer Facing and
Facility Facing, **not** nested inside them:

`Customer Facing | Facility Facing | Drivers | Customer Charges / Payments`

Each new section follows the exact same shell as the existing two: KPI row → global filter
bar → secondary (underline) tabs with tables/lists → activity timeline + info card(s) +
quick-actions side panel. Same pink/white design system, full dark mode, responsive
(tables collapse to cards under `md`).

### Drivers section
- **10 KPI cards:** Active Drivers, Drivers Online, Pickups Assigned, Deliveries Assigned,
  Pickups Completed Today, Deliveries Completed Today, Delayed Pickups, Delayed Deliveries,
  Avg Pickup Time, Avg Delivery Time.
- **5 secondary tabs:** Driver Overview · Pickup Queue · Delivery Queue · Driver Performance ·
  Driver Issues.
- **Driver Overview table:** name, status, zone, assigned, done today, delayed, rating/PPI,
  last active, actions (View Route / Contact / Assign).
- **Pickup Queue table:** order, customer **area** (privacy), service, pickup slot, driver,
  status, priority, notes, actions.
- **Delivery Queue table:** order, customer **area**, service, delivery slot, driver, facility,
  status, payment status, actions.
- **Driver Performance table:** completed, on-time %, avg pickup, avg delivery, rating, PPI.
- **Driver Issues table:** issue id, driver, order, issue type, priority, status, reported,
  action needed. Issue types include: Driver not reachable, Customer not available, Location
  unclear, Pickup delayed, Item photo missing, Payment collection issue.
- **Quick actions:** Assign / Reassign Driver, Mark Pickup Started / Picked Up / Delivery
  Started / Delivered, Report Issue, Contact Driver, View Route, Track ETA.

### Customer Charges / Payments section
- **10 KPI cards:** Total Customer Charges, Paid Orders, Pending Payments, Failed Payments,
  Refund Requests, Adjustments Pending, Cash / Pay on Delivery, Card / Online Payments,
  Invoice Payments, Payment Issues Open.
- **6 secondary tabs:** Payment Overview · Pending Payments · Refund Requests ·
  Adjustments / Extra Charges · Payment Issues · Invoices / B2B.
- **Payment Overview table:** order, customer, service, amount, method, payment status, charge
  status, city/area, source channel, details action.
- **Pending Payments table:** order, customer, amount due, method, due status, delivery status,
  follow-up needed, action.
- **Refund Requests list:** refund id, order, customer, amount, reason, order status, payment
  status, urgency, **human approval status**, actions — every refund shows *Approval Required*.
- **Adjustments / Extra Charges list:** order, customer, original + extra = final amount,
  reason, approval status, mock Approve/Reject.
- **Payment Issues table:** issue id, order, customer, issue type, amount, method, priority,
  assigned team, status, action.
- **Invoices / B2B table:** invoice id, business customer, service, amount, billing period,
  status, due date, Send action.
- **Two info cards** in the side panel: *"Operational payment view — financial summaries remain
  in the Finance section"* and *"Mock-only · Stripe off — refunds & adjustments require human
  approval; no card numbers/CVV/bank details stored."*
- **Quick actions:** View Payment Details, Mark as Paid (mock), Request Follow-up, Raise Refund
  Review, Approve/Reject Adjustment (mock), Send to Finance, Add Internal Note.

## 3. Finance vs Customer Charges / Payments
No duplication. **Customer Charges / Payments** = operational, customer/order-level payment
management (who owes, which refund needs review, which charge failed, which invoice is unpaid).
**Finance** = executive analytics (revenue, cost, margin). An info card in the new section states
this explicitly.

## 4. Files created
- `apps/admin/components/dashboard/operations/Drivers.tsx`
- `apps/admin/components/dashboard/operations/CustomerChargesPayments.tsx`
- `docs/build-reports/2026-07-21-operations-drivers-payments-sections.md` (this file)

## 5. Files modified
- `apps/admin/app/(dashboard)/operations/page.tsx` — added Drivers + Payments as top-level tabs;
  updated page description to "four operational surfaces".
- `apps/admin/lib/dashboard/operations-data.ts` — added Drivers + Payments mock data, types and
  tone maps (drivers, pickup/delivery queues, driver performance/issues; payment records, pending,
  refunds, adjustments, issues, invoices; activity feeds; tone maps + `dueStatusTone`).
- `apps/admin/lib/dashboard/filters.ts` — exported `facilityCity`; added `filterDrivers` and
  `filterPayments`; imported the two new row types.
- `docs/architecture/internal-dashboard-ui.md` — documented the 4-tab Operations structure.
- `docs/checklists/internal-dashboard-ui-test-script.md` — added Drivers + Payments test steps.
- `docs/00-Home.md` — linked this build report.

## 6. API endpoints / DB
None. No backend, migrations or API changes. Pure frontend mock data.

## 7. Filter behavior
- **Drivers:** market/region/city filter drivers by home zone/city (`filterDrivers`) and filter
  pickup/delivery queues by customer area (`filterByArea`). Service filters the queues. Channel
  does not apply to driver rows → passed through safely.
- **Payments:** Payment Overview supports all dimensions (market/region/city via area, service,
  channel, date range) through `filterPayments`. Pending/Refunds/Adjustments/Issues filter by
  area (+ service where present) via `filterByArea`. Invoices are B2B with no area dimension →
  passed through unfiltered (documented in code).

## 8. Privacy / security notes
- **Drivers:** tables show customer **area/city only** (e.g. "Dubai · Dubai Marina"), never full
  address, name, phone or email. A "Privacy firewall on" card states this. Full address is
  reserved for a future authorized detail view.
- **Payments:** customer name is shown (consistent with the customer-facing Orders table — this
  is the ops team's customer view), but **no card number, CVV, bank details or unmasked phone**.
  Only amount, method label, status, order id and area. Refunds & adjustments are explicitly
  labelled mock-only and *human approval required*.

## 9. What is mock-only / deferred
- **All of it is mock-only.** No live Stripe, no payment gateway, no live driver app, no live
  WhatsApp/LLM. Mark as Paid / Approve / Reject / Send to Finance are simulated (no state
  mutation, no charge, no refund).
- Deferred: wiring actions to real state/backend, live payment/driver integrations, classifier
  alert routing (section is *prepared* for it — see §11 — but no live alerts yet), authorized
  full-address detail view for drivers.

## 10. Tests / checks run (honest results)
| Check | Command | Result |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | ✅ 0 errors |
| Production build | `npx next build` | ✅ Passed (18/18 pages). `/operations` = 23.9 kB. Only warning is pre-existing (`conversations` useMemo dep, unrelated). |
| Lint | `npx next lint` | ✅ No errors in new files |
| Browser — Drivers (light) | Playwright | ✅ Renders: 4 top tabs, 10 KPIs, tables, timeline, actions |
| Browser — Payments (light) | Playwright | ✅ Renders: 6 sub-tabs, KPIs, tables, 2 info cards |
| Browser — dark mode | Playwright (theme toggle) | ✅ `dark` class applied, both sections styled correctly |
| Browser — mobile (390px) | Playwright | ✅ `scrollWidth == clientWidth` → no horizontal overflow; tables become cards |
| Console errors | Playwright listener | ✅ Only 2× `ERR_CONNECTION_REFUSED` from the WhatsApp-agent API backend (not running) — unrelated to these UI sections |

## 11. Classifier alert readiness (mock only)
Sections are structured so future classifier alerts route cleanly: refund request → Payments +
Customer Facing; duplicate charge → Payments + Finance; delayed pickup → Drivers + Customer
Facing; missing pickup photo → Drivers + Facility Facing; payment failed → Payments; cash not
collected → Drivers + Payments; B2B invoice overdue → Payments + Sales/Finance. These are
represented today only as mock rows/activity (e.g. "Cash not collected" driver issue + payment
issue on the same order LK-24805/1024).

## 12. Known limitations
- Buttons are non-functional (mock UI); no persistence.
- KPI numbers are illustrative, not derived from the row data.
- Invoices tab ignores global filters (no geo dimension).
- Driver Issues/Performance tabs are not geo-filtered (no area on those rows) — documented.

## 13. How to verify manually
```bash
cd "D:/Laundry Khalas App/apps/admin"
npm run dev           # http://localhost:3000/operations
```
Open `/operations` → confirm 4 top tabs. Click **Drivers**: 10 KPIs, 5 sub-tabs, driver table,
pickup/delivery queues (area only), performance, issues. Click **Customer Charges / Payments**:
10 KPIs, 6 sub-tabs, LK-AE-1024..1027 + 2031 with correct amounts/methods/status, refund/
adjustment approval labels, both info cards. Toggle dark mode. Resize to mobile — no overflow.

## 14. Next recommended step
Wire the classifier alert routing (mock → real) into these sections, or connect a mock
"Mark as Paid / Approve refund" to the existing order store so payment status actually mutates
(mirroring the stateful-orders work). Live Stripe and live driver app remain explicitly deferred.
