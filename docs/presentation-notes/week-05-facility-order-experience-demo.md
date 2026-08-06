# Presentation Notes — Facility Order Experience Redesign (Week 05)

## 1. What we can show in the demo
- The redesigned facility **order card**: id + priority + status, then **Required Work**, an important-notes indicator, **photo thumbnails**, items · due · fee · **next action**.
- The **order detail**: review-acknowledgement banner (gates Start Processing), critical-notes banner, Required Work, prioritized Important Notes, a **photo gallery with a full-size lightbox** (zoom/next/prev/caption/source), per-item breakdown, facility fee, revised-quote panel.
- **Raise an issue** with an item target + photo attach → it appears immediately in the Operations dashboard.
- **Revised quote**: facility submits a fee → Ops approves (backend computes the customer price) → customer approves → the order unblocks.

## 2. Suggested demo flow
1. Open the order list — point out that each card now says *what to do*.
2. Open an order — try **Start Processing**; it's blocked until you tap **"I have reviewed the details, notes and photos."**
3. Show the prioritized notes (a CRITICAL "do not alter the waist" stands out) and open a photo in the lightbox.
4. Raise an issue (e.g. *Existing damage detected*) with a photo → switch to the admin app and show it under Facility Facing with the photo + requirement chips.
5. Submit a revised quote → in admin, approve it (customer price appears) → mark customer approved → the order can advance again.

## 3. Screenshots needed
Order card, order detail (top hierarchy), photo lightbox, item breakdown, acknowledge banner, raise-issue form, admin issue detail with photos + revised-quote card.

## 4. Talking points
- Facilities no longer read raw JSON or the WhatsApp chat — they see grounded, structured work.
- Nothing shown to a facility is invented by AI: Required Work, notes and prices are computed from confirmed data.
- Money is safe: facilities see only their own fee + payout; margins, Stripe fees, other facilities' rates and the customer amount are never exposed.

## 5. Technical explanation in simple language
One backend "serializer" assembles a clean, permission-checked package per order; the dashboards just render it. New instructions or photos automatically mark the facility's review out-of-date so they re-check before working.

## 6. Business value
Fewer mistakes and back-and-forth with Operations, faster turnaround, a clear audit trail, and a professional partner experience.

## 7. Before vs after
Before: card showed id/service/status/time; work, notes and photos were buried or absent. After: the card leads with the work, surfaces critical notes and photos, and states the next action.

## 8. Risks/caveats to mention honestly
Live end-to-end needs the 3 migrations applied and the stack running; per-order facility-fee totals appear once handoff wiring populates the snapshot; the customer-approval step is recorded by Operations in the MVP (no live customer channel yet).

## 9. What is coming next
Populate the fee snapshot at handoff, run a live E2E pass with screenshots, and (if wanted) a live customer-approval channel and item-level pause granularity.
