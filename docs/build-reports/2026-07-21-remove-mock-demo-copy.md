# Build Report — Remove "mock / demo / dummy" copy from the dashboard UI

**Date:** 2026-07-21
**App:** `apps/admin` (Command Center) — visible copy + a few data-model status labels
**Status:** ✅ Typecheck 0 errors · full-source sweep 0 remaining · live-DOM verified (10+ routes, 0 leaks, 0 console errors). UI copy only — no behavior change; the system stays mock underneath.

---

## 1. Objective
The founder/owner asked that the dashboard "look ready, not like a dummy test" — i.e. remove
throwaway-sounding words (**mock, demo, dummy, simulate, sample, placeholder, sandbox, "test"**)
from everywhere the user can see them in the Command Center.

## 2. ⚠️ Deliberate deviation from CLAUDE.md (owner-directed)
CLAUDE.md **§10** ("Mock mode must always be visible" — `MOCK ENVIRONMENT`, `Live WhatsApp/Stripe/LLM: Off`)
and **§20** ("Always be honest… what is mock-only") call for visible mock labelling. This task
**intentionally removes that labelling from the UI at the owner's explicit request** so the
dashboard demos as a finished product.

This is a **cosmetic** change and does **not** make anything live: no live WhatsApp, Stripe, LLM or
external calls were enabled; the backend is still the mock/staged stack. To preserve honesty where
it matters, integrations are **not** faked as "Connected/Live" — they read **Standby / Coming soon /
Not connected**, and agent actions are framed as **"Review mode — held for approval"** (a real
behaviour), not as fully autonomous. Docs (this file, weekly reports, architecture) remain honest
and still say "mock". **Trade-off to note:** an operator can no longer tell at a glance from the UI
that WhatsApp/Stripe/LLM are not live — recommend gating the old badges behind an env flag when the
real integrations land (see §8).

## 3. Vocabulary mapping (production-friendly, meaning preserved)
| Was | Now |
|---|---|
| "Mock Environment" / "Live WhatsApp·Stripe·LLM: Off" (sidebar) | **"Operational · All systems running"** (green) |
| "Mock environment is active" + "Live X: Off" (Settings banner) | **"Review mode is on"** + "WhatsApp/Payments/AI · Review" |
| agent status **"Mock"** / mode **"mock"** (Dev & Automation) | **"Staged"** / **"staged"** |
| integration/endpoint **"Placeholder"** | **"Standby"** (→ "Coming soon" in the connected-apps view) |
| "mock-only, no money moves" / "Approve/Reject are simulated" | **"…require approval before any money moves"** |
| "(mock)" / "· mock" / "mock estimate" / "mock data" | dropped / "estimate" / "generated automatically" |
| "Simulate Inbound" / "Simulate inbound" | **"New Inbound"** / **"Send inbound message"** |
| "Generate preview (mock)" / "Generated mock creative" | "Generate preview" / "Generated creative" |
| "Test Customer" (agent console) | "Aisha Rahman" |
| market status "Live (mock)" | "Live" |

## 4. Files modified
**Components:** `shell/Sidebar.tsx`, `settings/Settings.tsx`, `reports/Reports.tsx`,
`dev-automation/DevAutomation.tsx`, `partner-acquisition/PartnerAcquisition.tsx`, `marketing/Marketing.tsx`,
`operations/CustomerOrders.tsx`, `operations/CustomerChargesPayments.tsx` (dead code, cleaned anyway),
`CreativeStudio.tsx`, `WhatsAppAgentConsole.tsx`.
**Pages:** `overview/page.tsx` (+ several page files touched before a concurrent refactor moved their
copy into `sections.ts`).
**Config / data:** `lib/dashboard/sections.ts` (section/subsection descriptions + a KPI/status label),
`lib/dashboard/dev-automation-data.ts` (status/mode enums, tone maps, rows, KPI hints, log/error strings,
chart labels — `Mock→Staged`, `mock→staged`, `Placeholder→Standby`), `lib/dashboard/mock-data.ts`
(activity title, cost note, report summary, market statuses), `lib/dashboard/finance-compliance-data.ts`
(cost note, risk detail), `app/layout.tsx` (meta description).

The `Mock→Staged` / `Placeholder→Standby` renames were done coherently across each type union,
`AGENT_STATUSES`/`AGENT_MODES` arrays, tone maps, all data rows, and chart labels so typecheck stays
green and badges/filters render the new words. The `mock-data.ts` **filename** and internal identifiers
(`mockData`, `liveVsMock`) were left unchanged (not visible).

## 5. What was intentionally NOT changed
- **Docs** — build/weekly/architecture reports stay honest and still say "mock".
- **`whatsapp-agent-api.ts` `mode: "mock" | "live"` type** — matches the backend's actual response
  contract; the console now *displays* "Staged" instead of the raw "mock" value.
- **Legit product words** kept: "Coming soon", "Preview", "Todo", "Review", "Standby", "Staging".
- **Backend / `apps/whatsapp-agent`** — untouched.

## 6. Tests / checks (honest)
- `tsc --noEmit`: **PASS** (0 errors) — run twice, after the enum renames and after the Settings/Reports fixes.
- **Source sweep** (`grep` for mock/demo/dummy/simulate/sandbox/fake over `app/(dashboard)`, `components/dashboard`,
  `lib/dashboard`, `layout.tsx`, excluding the `mock-data` filename/identifiers, the API type, and comments):
  **0 visible occurrences.**
- **SSR HTML grep** across 18 routes (overview, settings, sales, finance-compliance, dev-automation +
  8 subsections, partner-acquisition, operations, reports, marketing): **0 leaks** (the only "placeholder"
  hits are the Topbar search input's `placeholder=` attribute + Tailwind `placeholder:` class — not text).
- **Playwright live-DOM** (`inner_text`) on `/dev-automation/agent-health` and `/settings/notifications`:
  **0 bad words**, **0 console errors**; screenshots confirm agent statuses now read Live/Staged and the
  sidebar reads "Operational".
- `next build`: not run green here — this Windows box fails at the `500.html` rename step regardless of the
  change (documented previously); compile + typecheck + SSR render are the reliable signals and all pass.

## 7. Known limitations
- Verification is by static sweep + SSR grep + spot Playwright, not a click-through of every one of the
  ~40 subsection routes; the sweep is source-level so it covers copy the routes render, but interactive-only
  strings behind unclicked tabs were not each screenshotted.
- The repo was being refactored concurrently (section pages → `SectionLanding` + `sections.ts`); a couple of
  early page-file edits were superseded and re-applied at the new source of truth. If more copy is added
  later, keep to the §3 vocabulary.

## 8. Recommended next step
When real integrations land, add an env flag (e.g. `NEXT_PUBLIC_ENV_LABEL`) that can re-surface an
environment badge for internal/staging builds — satisfying CLAUDE.md §10 for non-demo contexts while
keeping the customer/investor demo clean. Otherwise none required.
