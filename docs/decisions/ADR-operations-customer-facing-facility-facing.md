# ADR — Operations split: Customer Facing vs Facility Facing

**Date:** 2026-07-20
**Status:** Accepted
**Context:** The Operations dashboard section was a single mixed area
(conversations, orders, tickets, drivers, changes). The team needs to run
customer-side and facility-side workflows separately.

## Decision
Split `/operations` into **two top-level teams** via a segmented switch:

1. **Customer Facing** — WhatsApp Agent console, customer orders, tickets/
   concerns, order changes, cancellations, follow-ups.
2. **Facility Facing** — facility order queue, facility assignment + management,
   status updates, facility issues, quality checks, delivery handoff.

Each team owns: a distinct KPI row, a filter bar, secondary (underline) tabs for
its tables, an activity timeline, and a quick-actions panel.

## Rationale
- **Different jobs, different data.** Customer support and facility operations
  share almost no columns; one table served neither well.
- **Privacy by construction.** The strongest reason. Facility-facing screens must
  not expose customer PII (CLAUDE.md §7 privacy firewall). Splitting lets the
  facility side show **area/city only** — no name, phone, email, full address or
  complaint notes — with no risk of a shared component leaking a customer field.
- **Clarity for staff.** Two clearly labelled surfaces map to two real teams.

## Privacy rules encoded
- **Facility Facing:** `operations-data.ts` facility records intentionally carry
  no customer identity — `area` (city · district) only. A "Privacy firewall on"
  banner is always visible on the tab. Verified: 0 phone-like strings render.
- **Customer Facing:** support context is shown, but phone numbers are masked
  (`maskPhone`) and sensitive info is minimised.

## UI decision
Added a `segmented` variant to the shared `Tabs` component for the top-level team
switch, so the nested underline secondary tabs clearly read as a sub-level (avoids
two identical tab rows). Pink/white theme, full dark mode, responsive (tables →
cards on mobile), no overlays.

## Consequences
- The previous single-level Operations tabs are superseded; the live WhatsApp
  Agent console now lives under Customer Facing → WhatsApp Agent.
- Facility state changes and filters are still mock/presentational (deferred).

Related: [[privacy-firewall]] · [[internal-dashboard-ui]] ·
[[ADR-internal-dashboard-design-system]] · [[2026-07-20-operations-team-split]]
