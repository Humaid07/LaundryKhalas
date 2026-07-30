# Week 3 Report

Covers **2026-07-29** (the WhatsApp Operations Agent tuning program). Follows
[[week-02-report]]. Headline: the customer-facing WhatsApp agent was **tuned to the
founder-approved specification** — a real negotiation engine replaces the old automatic
discount, plus min-order/express pricing, AED/QAR plumbing, a single persona, route-to-human
categories, adversarial privacy tests, and a §12 regression suite + replay harness. All
mock-first; nothing live was enabled. Test counts below were run this session unless noted.

## 1. Executive summary
The agent now follows the founder's confirmed rules. It quotes the **full website price** and
only discounts through a **negotiation ladder** (10→20% under AED 100, 15→25% over) with a
protected **facility-floor** (`floor = discounted − 0.75×(discounted − cost)`); it charges the
min-order delivery fee, prices Express at +50% with a 3 PM cut-off, speaks as one persona in
English/Arabic, quotes only in the customer's currency, routes villa/wedding/luxury work to a
specialist, and never leaks customer PII to facilities/drivers. Delivered in 7 staged, reviewed
slices, each with tests + a build report.

## 2. What shipped this week
- **Negotiation-only discount model** — retired the automatic 15%-over-100 discount (rollback
  flag kept); new `negotiate_order_price` tool driving the §3 ladder + facility-floor + escalation.
- **Rules/config layer** — negotiation, min-order/delivery (≥50 free / <50 → 8), Express +50% &
  3 PM cut-off, AED/QAR currency plumbing, carpet turnaround 2–5 days, persona.
- **System prompt** — persona (single name, never-reveal-AI, en/ar), §2.12 order flow (photo-gate,
  full-address capture, driver 15–30 min + reception/security/door fallbacks, special-care notes,
  alterations cm/inch), payment guardrails, AED/QAR overlay.
- **Tools** — `quote_express`, delivery fee in the summary, `route_to_specialist`.
- **Routing** — villa/home cleaning, wedding dresses, luxury/couture → specialist (never quoted).
- **Privacy** — adversarial tests proving no phone/email/full-address reaches facility/driver output
  or the model-facing state block.
- **Regression** — 14 §12 scenario tests + a runnable `scripts/replay_scenarios.py` (14/14 pass).

## 3. What changed since last update
The agent's discount behaviour changed materially: full price is quoted by default and discounts
come only from negotiation. Wedding dresses now route to a specialist instead of being quoted as
Clean & Press. Carpet turnaround corrected 3–4 → 2–5 days.

## 4. Screens/features ready to demo
No new UI. Demo is via the agent's backend + the replay harness (`scripts/replay_scenarios.py`)
and the test suites. See [[week-03-whatsapp-agent-tuning-demo]].

## 5. Backend progress
7 config files + 4 new pure services (`negotiation`, `fulfilment`, `market`, `specialty_routing`),
plus additions to `pricing`, `booking_flow`, `delivery`, `service_resolution`, `rules`, `settings`,
and the Claude booking tools/prompt.

## 6. Frontend progress
None this week (agent-only scope).

## 7. Agent progress
Persona, negotiation, min-order/express pricing, currency overlay, specialist routing, promo
suppression during complaints — all mock-first and prompt/tool-gated. The backend (never the model)
decides every price/discount/route.

## 8. Database progress
**No migration** — negotiation state reuses existing discount columns; routing uses the existing
pending-tasks table. `delivery_sla_rules` needs a re-seed (carpet/express) before live use.

## 9. Security/privacy progress
Dedicated adversarial privacy suite added; facility/driver output + the model-facing state block
proven PII-free.

## 10. Testing progress
286 passed across the 17 program-touched suites; 14/14 replay scenarios; ruff clean on all changed
files. Full suite not run (large; targeted runs per README).

## 11. Blockers
None technical. Two founder inputs gate go-live (below).

## 12. Risks
- The **facility-floor cost basis** is unconfirmed, so the deepest negotiation tier currently
  escalates to a human rather than auto-offering the floor (safe, but not the full §3.2 experience).
- QAR is plumbed but unpriced — QAR customers route to a human.

## 13. Decisions needed from founder/team
1. **Set `agent_name`** (single persona name).
2. **Confirm the facility-floor cost basis** (how a facility's cost-per-order is derived) so the
   live facility-cost lookup can be wired.
3. **Provide the Qatar (QAR) price list** to enable QAR quoting.

## 14. Deviations from roadmap/spec
Facility-floor is engine-complete but not yet reachable end-to-end (cost lookup deferred pending the
decision above). Ghost-timer auto-advance deferred (needs a scheduler). Min-order/express engines
built in Stage 1; exposed as tools in Stage 3b.

## 15. Next week's plan
Wire the live facility-cost lookup + re-seed the SLA table once the cost basis is confirmed; set the
persona name; load the QAR price list; then a live-WhatsApp readiness review.

---

## Addendum — 2026-07-30 (Admin UI polish)

Separate from the agent workstream, one **admin dashboard UX fix** shipped:

- **Dashboard search → inline suggestions dropdown.** The topbar search used to open a
  centered **modal with a full-screen dimming + blur backdrop**, so the whole dashboard
  "popped"/darkened on every search. It's now a real **input in the topbar** whose
  suggestions render in a dropdown **anchored under the bar** (a fixed sheet under the
  header on mobile) — **no overlay, no page dimming, no page blur; the dashboard
  background stays stable.** The dropdown got a premium **dark teal-tinted gradient card**
  with hover + keyboard-active states, a clean empty state, and a soft entrance animation.
  Keyboard nav (↑/↓/Enter), Esc, and click-outside all preserved. Theme-aware (reads well
  in light **and** dark). New `TopbarSearch` component; old `CommandPalette` modal removed.
  Gates: typecheck + lint clean (one pre-existing unrelated warning), production build ✓,
  and a **15/15 Playwright** behavioural suite (desktop + mobile). Build report:
  `build-reports/2026-07-30-dashboard-search-dropdown.md`. Demo:
  `presentation-notes/week-03-dashboard-search-demo.md`.
- **Search dropdown made solid + amber highlight, and Overview sections made collapsible.**
  Follow-up to the above: the dropdown is now a **fully opaque surface** (removed the teal
  gradient + backdrop-blur, so dashboard content no longer shows through), and its
  hover/selected highlight moved to a **warm amber/gold** accent (distinct from the heavy
  teal). The **Overview page** gained **collapsible sections** (Headline totals, Trends,
  Breakdowns, Orders & approvals, Conversations & activity) — header stays visible, content
  folds with a smooth height animation, state **persists in localStorage**, plus **Expand
  all / Collapse all**. No data/cards/routes removed. Gates green + **18/18 Playwright**.
  Build report: `build-reports/2026-07-30-search-solid-and-overview-collapse.md`.
- **Sidebar: whole parent row now toggles its submenu.** Sections with subsections
  (Operations, Sales, Partner Acquisition, SEO Agents, Marketing, Finance & Compliance,
  Dev & Automation, Reports) expand/collapse when the **whole row** is clicked, not only
  the chevron — the parent row is now a proper disclosure `<button>` (Enter/Space work).
  Leaf items (Overview, Orders) still navigate. To keep each section's landing reachable,
  a first **"Overview" child** (→ the section landing, `exact`-highlighted) was added.
  No visual redesign — same layout/colors/icons/badges/chevron. Gates green + **30/30
  Playwright** (desktop + mobile). Build report:
  `build-reports/2026-07-30-sidebar-parent-row-toggle.md`.
- **Inbox filter pills → compact Filter button + popover.** In Operations → Customer
  Facing, the five filters ("All / Human Needed / Urgent / Active Orders / Resolved")
  used to sit **permanently as a pill wall** above the chat list, eating vertical space.
  They now live behind **one compact funnel Filter button** beside "Search chats" that
  opens a focus-managed **popover**: **Attention** (Human Needed / Urgent — multi-select
  **checkboxes**, since a chat can be both) and **Order status** (Active Orders / Resolved
  — **radios**, since they're mutually exclusive), each with a **live count** from the real
  conversation data. Active filters show as a **badge on the button** + a **one-row
  removable summary chip** (e.g. "Human Needed +1 ×") — no pill wall. Search + filters
  **combine (AND)**; there's a proper empty state ("No conversations match…" + Clear
  filters); the selected chat **safely deselects** if a filter hides it. Filter state is
  **persisted in the URL** (`?human_needed=true&urgent=true&order_status=active`) so it
  survives refresh and back/forward. Three-column layout, chat pane, colours and spacing
  unchanged. Fixed an async-router race during the build (local state is now the instant
  source of truth, mirrored to the URL). Gates: typecheck + lint clean; Playwright verified
  (desktop, dark, mobile — all 15 requested cases). Build report:
  `build-reports/2026-07-30-inbox-filter-popover.md`.
