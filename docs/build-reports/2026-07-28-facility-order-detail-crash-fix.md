# Build Report — Facility Dashboard order-detail crash fix (defensive line-item formatting)

**Date:** 2026-07-28
**Area:** `apps/facility-dashboard` (frontend) + `apps/whatsapp-agent` (facility DTO)

## 1. Objective
Fix a runtime crash on the Facility Dashboard order-detail page and harden all
customer/facility-facing line-item rendering against untrusted API/Supabase data.

## 2. The bug
Opening an order detail (e.g. `http://localhost:3010/orders/LK-2026-000005`)
crashed with:

```
Runtime TypeError: li.pricing_unit.toLowerCase is not a function
app/(app)/orders/[orderId]/page.tsx  (~line 204)
```

**Root cause.** The backend serializes each line item from the order snapshot as
`{name, quantity, measure}`, where **`measure` is a numeric value** — "sqm for
per-sqm items or kg for additional-weight lines" (`services/pricing.py`). The
frontend mapper aliased `measure → pricing_unit` (a field the UI treated as a
text unit) and called `.toLowerCase()` on it directly. For `LK-2026-000005`
("Carpet — Regular"), `measure = 30.0` (a number), so `.toLowerCase()` threw and
crashed the whole page. Any non-string (`null`, number, object, missing) hit the
same path.

## 3. What was changed

### Frontend (`apps/facility-dashboard`)
- **`lib/formatters.ts`** — added `formatPricingUnit(value: unknown): string`
  (string→trim+lowercase, number→string, null/undefined/object→"") and
  `formatQuantity(value: unknown): string`. Anything unrenderable returns "" so
  callers hide the separator instead of crashing.
- **`app/(app)/orders/[orderId]/page.tsx`** — line-item render now uses
  `formatPricingUnit(li.pricing_unit)` + `formatQuantity(li.quantity)` and only
  shows the ` · unit` separator when non-empty. Also routed the status→action
  lookup through `statusToken(order.status)` instead of `order.status.toLowerCase()`.
- **`lib/api-client.ts`** — `FacilityLineItem.pricing_unit` widened to
  `string | number | null` (honest to reality); mapper keeps raw values and no
  longer pretends `measure` is a string.
- **`lib/status.ts`** — every status/sla/task/role helper now accepts `unknown`
  and routes through a `norm()` guard, so a numeric/object/null status can never
  reach `.toLowerCase()`/`titleCase`. Exported `statusToken(unknown)` for safe
  equality checks/Set lookups.
- **`app/(app)/drivers/[driverId]/page.tsx`**, **`app/(app)/issues/[issueId]/page.tsx`**,
  **`components/drivers/DriverIssuePanel.tsx`** — replaced `(x ?? "").toLowerCase()`
  status comparisons with `statusToken(x)`.

### Backend (`apps/whatsapp-agent`)
- **`db/repositories/facility_orders_repo.py`** — `_item_breakdown` now emits a
  clean, type-coerced DTO: `{name: str, quantity: float|None, measure: float|None}`
  via a new `_num()` coercion helper. The API can no longer ship an object/junk
  where the dashboard expects a scalar. PII-safety unchanged.

## 4. Mock/live
No behavior change to live vs mock. Pure defensive formatting + type coercion.

## 5. Privacy
No new fields exposed; the facility DTO remains PII-safe (name + numeric
quantity/measure only). No customer contact/address/payment leaked.

## 6. Tests & checks
- **Backend:** `pytest tests/test_facility_orders.py` → **24 passed** (added 4
  normalization tests: numeric `measure`, object/string/junk → `None`, legacy
  `items` fallback, empty/missing `line_items`, plus a `_num` coercion table).
- **Frontend:** `npm run typecheck` clean; `npm run lint` clean (one pre-existing
  unrelated warning in `orders/page.tsx`); `npm run build` succeeded (20/20 routes,
  built to an isolated `LK_DIST_DIR` so the running dev server was untouched).
- **Manual (Playwright, headless):** `/orders/LK-2026-000005` renders
  "Carpet — Regular  ×1 · 30" with **no `toLowerCase` crash and no console errors**;
  `/orders/LK-2026-000004` also renders. Screenshot captured.

## 7. Known limitations
- The facility dashboard has no JS unit-test runner, so `formatPricingUnit`'s
  cases are covered by typecheck + build + the Playwright render check rather than
  a Jest/Vitest suite; the equivalent normalization is unit-tested on the backend.
- A numeric `measure` (sqm/kg) renders as a plain number suffix ("×1 · 30") — safe
  and informative, but not labelled with its unit; a future improvement could
  carry the unit label alongside the measure.

## 8. How to verify manually
1. Ensure backend (`:8100`) + facility dashboard (`:3010`) are running.
2. Open `http://localhost:3010/orders/LK-2026-000005` → page renders, Items shows
   "Carpet — Regular  ×1 · 30", no runtime error.
3. Open another order (e.g. `LK-2026-000004`) → renders normally.
