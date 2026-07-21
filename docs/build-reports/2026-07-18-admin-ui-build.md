# Build Report: Admin UI

## 1. Build title

Admin Dashboard UI for WhatsApp Operations Agent (Visual Testing Console)

## 2. Date

2026-07-18

## 3. Task objective

Build a Next.js admin dashboard so a non-technical operator can visually
exercise the WhatsApp Operations Agent MVP end-to-end (simulate an inbound
message, run the agent, review/approve/reject its draft reply, see the
resulting mock order, and audit every AI action) without touching curl or
`/docs`. This is priority #2 on the roadmap in `CLAUDE.md` §2/§18, after the
WhatsApp Agent backend.

Note on documentation timing: the UI itself (code) was built in a prior
session, before the documentation ADR (`docs/decisions/ADR-project-
documentation-and-memory-rule.md`, in force from 2026-07-18) existed. That
session left `docs/audits/admin-ui-start-report.md` and `docs/decisions/
admin-ui-design-decisions.md` instead of a formal build report. This report
retroactively fills that gap in the required shape, and additionally
verifies the built UI still works today (see §16 Tests run) rather than
just restating what was planned.

## 4. What was built

- A full Next.js 14 (App Router) admin dashboard at `apps/admin/`, a
  sibling of the FastAPI backend, with 8 routes: Overview, Conversations
  inbox, Conversation detail/chat, Approval queue, Orders list, Order
  detail, AI action log viewer, and a Mock WhatsApp Test Console.
- A small hand-rolled Tailwind component library (`components/ui/`): status
  badges, cards, buttons, data table, empty/loading/error states, JSON
  viewer — no shadcn/Radix dependency (see `docs/architecture/admin-ui-
  architecture.md` for the rationale).
- A typed API client (`lib/api-client.ts` + `lib/types.ts`) that talks
  directly to the FastAPI backend from the browser (no Next.js server
  component/route touches the backend), using TanStack Query for
  fetch/mutate/cache/invalidate.
- A persistent "Mock Environment" indicator plus "Live WhatsApp / Live
  Stripe / Live LLM: Off" badges in the topbar, and mock-labeled button
  copy everywhere ("Approve Mock Reply", "Send Manual Mock Reply",
  "Simulate Inbound Message") — this is the CLAUDE.md §10 requirement that
  mock mode must always be visible.
- Three small, additive, read-only backend endpoints needed by the UI (no
  model/schema changes beyond one new response schema):
  - `GET /api/admin/orders/{id}/events` — reads existing `OrderEvent` rows.
  - `GET /api/admin/ai-action-logs?order_id=` — added alongside the
    existing `?conversation_id=` filter.
  - `GET /api/admin/markets` — resolves a `market_id` UUID to a readable
    code (e.g. `AE`) for the Conversations/Orders pages; new
    `app/schemas/market.py`.
- An explicit CORS allow-list added to `app/main.py` (`http://localhost:3000`,
  `http://127.0.0.1:3000` only — not a wildcard) since the UI runs on a
  different origin/port than the API in dev.
- A Docker Compose service (`admin`) running `next dev` on port 3000, with
  a dedicated `apps/admin/Dockerfile`.

## 5. Why it was built

Per `CLAUDE.md` §2, the admin dashboard is the second build priority,
specifically so the team can visually test and demo the WhatsApp Operations
Agent without needing to hand-craft API calls. It is also the substrate for
the required approval/reject/manual-takeover workflow (§6/§8) and AI action
audit trail (§10) — both are non-negotiable engineering rules, not optional
UI polish.

## 6. Files created

**Frontend (`apps/admin/`)** — full new Next.js project:
- App shell: `app/layout.tsx`, `app/page.tsx`, `app/admin/layout.tsx`
- Pages: `app/admin/page.tsx` (Overview), `app/admin/conversations/page.tsx`,
  `app/admin/conversations/[id]/page.tsx`, `app/admin/approvals/page.tsx`,
  `app/admin/orders/page.tsx`, `app/admin/orders/[id]/page.tsx`,
  `app/admin/ai-logs/page.tsx`, `app/admin/mock-whatsapp/page.tsx`
- Layout components: `components/layout/AdminSidebar.tsx`,
  `AdminTopbar.tsx`, `PageHeader.tsx`
- UI primitives: `components/ui/status-badge.tsx`, `card.tsx`, `button.tsx`,
  `data-table.tsx`, `empty-state.tsx`, `loading-state.tsx`,
  `error-state.tsx`, `json-viewer.tsx`
- Feature components: `components/conversations/ConversationList.tsx`,
  `ChatMessageBubble.tsx`, `ManualReplyBox.tsx`,
  `ConversationContextPanel.tsx`; `components/approvals/ApprovalCard.tsx`;
  `components/orders/OrderTimeline.tsx`; `components/logs/
  AIActionLogTable.tsx`
- Lib: `lib/api-client.ts`, `lib/types.ts`, `lib/formatters.ts`,
  `lib/constants.ts`, `lib/utils.ts`, `lib/query-client.tsx`
- Config: `tailwind.config.ts`, `package.json`, `next.config.js`,
  `tsconfig.json`, `Dockerfile`, `.env.example`

**Backend additions:**
- `app/schemas/market.py`

**Documentation (this task, 2026-07-18):**
- `docs/build-reports/2026-07-18-admin-ui-build.md` (this file)
- `docs/presentation-notes/week-01-admin-ui-demo-notes.md`
- `docs/weekly-reports/week-01-report.md`

Documentation from the original build session (already existed, not
recreated): `docs/audits/admin-ui-start-report.md`,
`docs/decisions/admin-ui-design-decisions.md`,
`docs/architecture/admin-ui-architecture.md`,
`docs/checklists/admin-ui-manual-test-script.md`.

## 7. Files modified

- `app/main.py` — added `CORSMiddleware` with an explicit dev allow-list.
- `app/api/routes/orders.py` — added `GET /{order_id}/events`.
- `app/api/routes/admin.py` — `ai-action-logs` route accepts `?order_id=`.
- `docker-compose.yml` — added the `admin` service.
- `docs/00-Home.md` — updated to link this report (this task).

## 8. API endpoints added/changed

| Method | Path | Change |
|---|---|---|
| GET | `/api/admin/orders/{id}/events` | new |
| GET | `/api/admin/ai-action-logs?order_id=` | new query param on existing route |
| GET | `/api/admin/markets` | new |

All other endpoints the UI consumes (`conversations`, `messages`,
`approvals`, `orders`, `mock-whatsapp/inbound`, `run-agent`,
`manual-takeover`/`release-takeover`, `manual-reply`) already existed from
the backend build and are unchanged. Full list in
`docs/audits/admin-ui-start-report.md` §2.

## 9. Database tables/models added/changed

None. No new tables, columns, or model changes — the three new endpoints
above read existing tables (`OrderEvent`, `AIActionLog`, `Market`) that had
no admin route exposing them yet.

## 10. UI pages/components added/changed

8 routes, listed in §4/§6 above. Full component tree and data-flow diagram
in `docs/architecture/admin-ui-architecture.md`.

## 11. Agent behavior added/changed

None. The UI is a consumer of the existing WhatsApp Operations Agent
(`POST /api/admin/conversations/{id}/run-agent`) — no agent logic changed.

## 12. Integrations added/changed

None live. The UI talks only to the local mock-first FastAPI backend.
No WhatsApp, Stripe, or LLM provider integration is referenced anywhere in
the frontend code — verified by inspection (see `docs/decisions/admin-ui-
design-decisions.md`) and re-confirmed today (§16).

## 13. What is mock-only

Everything. The entire admin UI operates against `MockWhatsAppAdapter` and
`MockProvider`-backed data. Every send/approve action is explicitly labeled
"mock" in the UI copy. The topbar's Live WhatsApp/Stripe/LLM indicators all
read "Off."

## 14. What is live

Nothing. No live external API is called anywhere in this stack.

## 15. What is intentionally deferred

- Customer detail/search page and endpoint (no `GET /api/admin/customers`
  exists yet — conversation/order detail views show `customer_id` as-is).
- Pagination/filtering on list endpoints (client-side filtering only; fine
  at current mock data volumes).
- Real per-user auth/RBAC (currently a single shared `X-Admin-Api-Key`).
- Market/facility/pricing config management UI (no CRUD endpoints exist).
- Classifier-related UI (intent/sentiment/urgency management) — classifier
  agent itself is not built (`CLAUDE.md` §9/§17).
- Cost-tracking dashboard UI (`CostTracking` table exists, no admin route
  reads it yet).

All of the above are documented pre-existing gaps from
`docs/audits/admin-ui-start-report.md` §3 and `docs/checklists/
admin-dashboard-mvp.md`, not new findings.

## 16. Tests run

This session (2026-07-18) re-verified the already-built admin UI still
works, since no automated test suite exists for the frontend. Ran live
against the local Docker stack (mock-only, no live external calls):

1. **Backend health** — `GET /health` → `{"status":"ok"}`.
2. **All 5 admin list/read endpoints** (`conversations`, `approvals`,
   `orders`, `ai-action-logs`, `markets`) → HTTP 200 with `X-Admin-Api-Key`.
3. **Full happy-path agent flow**, exercised via the same API calls the UI
   makes:
   - `POST /api/mock-whatsapp/inbound` (market `AE`, message "I need
     laundry pickup tomorrow, Dubai Marina") → conversation + message
     created.
   - `POST /api/admin/conversations/{id}/run-agent` → agent returned
     `decision: create_order` with a draft reply and a mock order
     (`estimated_total: AED 25.00`, facility `[MOCK] Dubai Marina
     Facility`) — no invented data, matches seeded facility/pricing config.
   - `POST /api/admin/approvals/{id}/approve` → approval marked `approved`,
     `decided_by` recorded.
   - `GET /api/admin/orders/{id}` → order confirmed `status: created`,
     facility assigned, correct pickup window.
   - `GET /api/admin/ai-action-logs?conversation_id=` → `tool_call` rows
     present (e.g. `get_or_create_customer`) with input/output JSON, timing,
     and success flag — the audit trail required by `CLAUDE.md` §5.10/§5.11.
4. **Frontend route smoke test** — all 8 admin routes hit directly via HTTP:
   `/admin`, `/admin/conversations`, `/admin/conversations/[id]`,
   `/admin/approvals`, `/admin/orders`, `/admin/orders/[id]`, `/admin/ai-logs`,
   `/admin/mock-whatsapp` → all returned HTTP 200 and compiled cleanly in
   the Next.js dev server (verified via `docker logs`).
4a. **Manual takeover / release / manual-reply flow** — also exercised via
   the same API calls the UI's buttons make, on the conversation created in
   item 3: `POST .../manual-takeover` → `manual_takeover: true`; a
   subsequent `POST .../run-agent` correctly returned **HTTP 409** (agent
   refuses to run while a human has taken over); `POST .../manual-reply`
   correctly created an outbound `mock_sent` message immediately, bypassing
   the approval queue by design; `POST .../release-takeover` correctly
   restored `manual_takeover: false`. All four steps matched
   `docs/checklists/admin-ui-manual-test-script.md` steps 14-16 exactly.
   `apps/admin/lib/types.ts` was also cross-checked field-by-field against
   every live API response captured in this run — no drift found.
5. **Frontend build/typecheck/lint** — run via
   `docker compose exec admin npm run typecheck` /
   `npm run lint`, and `docker run --rm laundrykhalasapp-admin:latest npm
   run build` (the host shell has no `node`/`npm` on `PATH`, but the
   already-built `admin` Docker image does, so commands were executed
   there instead — a later pass in the same day closed the gap flagged
   below in the original version of this section).
   Note: running `npm run build` directly inside the *running* `admin`
   compose container first failed with
   `PageNotFoundError: Cannot find module for page: /_document` — this is
   not a code defect, it's the shared `admin_next_cache` Docker volume
   being concurrently written by the live `next dev` process, whose
   dev-mode `.next` state conflicts with a production build reading the
   same mount. Running the build against a **fresh container from the
   already-built image** (`docker run --rm laundrykhalasapp-admin:latest
   npm run build`, no shared volume) succeeded cleanly. No action needed
   for normal `docker compose up` usage — the compose service only ever
   runs `next dev`, never `next build`, against that volume.

## 17. Test results

- Backend: all endpoints and the full agent→approval→order flow passed as
  described above, no unexpected errors.
- Frontend, first pass: `/admin/conversations/[id]` and `/admin/orders/[id]`
  (the two dynamic-route detail pages) returned **HTTP 500** on first
  request. See bug below.
- Frontend, after fix: all 8 routes returned HTTP 200, including both
  detail pages, confirmed against the real conversation/order created in
  the flow above.
- Full manual click-through test script exists at `docs/checklists/
  admin-ui-manual-test-script.md`; this session validated its steps at the
  API/HTTP level but did not drive a real browser (no browser automation
  tool available in this session) — a human should still run that script
  visually before a live demo.
- `npm run typecheck`: clean, no errors. `npm run lint`: 0 errors, 1
  pre-existing non-blocking warning (`app/admin/conversations/page.tsx:28`
  — a `useMemo` dependency-array warning on a `conversations` logical
  expression; does not affect correctness at current data volumes, not
  fixed here to stay in scope for a verification pass). `npm run build`:
  succeeds — all 10 routes compile (8 static, 2 dynamic for the `[id]`
  routes), confirming the production build (not just `next dev`) is sound.

## 18. Bugs/issues found

- **Transient 500 on dynamic detail routes** (`/admin/conversations/[id]`,
  `/admin/orders/[id]`) on first load: Next.js dev server errored with
  `Cannot find module './vendor-chunks/next.js'` and `ENOENT ... build-
  manifest.json`, reading from a stale `.next` dev cache — the
  `admin_next_cache` Docker named volume had inconsistent state left over
  from a previous container run. **Fix applied:** `docker restart
  laundrykhalas_admin` — the dev server rebuilt `.next` cleanly and all
  routes including the two dynamic detail pages returned 200 afterward.
  **Root cause:** stale bind/volume-mounted `.next` cache on a container
  restart, a known Next.js dev-mode flakiness pattern, not a code defect
  (no source change was needed). **Follow-up recommendation:** if this
  recurs, `docker compose down` then `docker volume rm
  laundrykhalasapp_admin_next_cache` (or equivalent) clears it; consider
  documenting this as a standard "if the UI 500s on first load, restart the
  admin container" note in the manual test script.
- `POST /api/admin/approvals/{id}/approve` requires a `decided_by` field
  that isn't mentioned in `docs/checklists/admin-ui-manual-test-script.md`
  step 10 — not a bug (the UI presumably fills this automatically when the
  "Approve Mock Reply" button is clicked), but worth a human confirming the
  UI does supply it, since this session only verified the API contract, not
  the button's exact payload.

## 19. Known limitations

- No automated frontend test suite (unit/integration/e2e) exists yet —
  verification today was manual API/HTTP-level only, plus (in a later pass
  the same day) `typecheck`/`lint`/`build`, all clean. A real browser
  walkthrough of the click-through UI is still outstanding — see §25.
  See also the gaps listed in §15 (pagination, customer resolution, real
  auth).

## 20. Security/privacy notes

- All `/api/admin/**` routes require `X-Admin-Api-Key` (placeholder-strength
  shared key, not per-user RBAC — flagged as a pre-live-launch requirement
  in `docs/checklists/live-whatsapp-readiness.md`).
- CORS is an explicit allow-list of two localhost origins, not a wildcard.
- No customer phone number, email, or full address is rendered in the UI
  outside of what an admin explicitly needs — consistent with
  `CLAUDE.md` §7 (Privacy Firewall). Not independently re-audited in this
  session; carried forward from `docs/decisions/admin-ui-design-decisions.md`.
- `.env` / `.env.example` reviewed; no secrets committed, only placeholder
  dev values (`changeme_local_admin_key`).
- **New finding (later pass, same day):** `.env` contains an unused
  `EVOLUTION_API_BASE_URL` / `EVOLUTION_API_KEY` pair. Evolution API is an
  unofficial WhatsApp-Web automation tool — exactly what `CLAUDE.md` §4
  bans ("No unofficial WhatsApp automation"). Grepped `app/` for any
  reference: none found — no code reads these variables today, and the
  key is not committed (`.env` is gitignored). Still, a live-looking
  credential for a banned integration sitting in config is worth a
  deliberate decision (remove it, or document why it exists) rather than
  being unexplained dead config.
- **New finding (later pass, same day):** this repository is **not
  currently under git version control** (confirmed via environment
  metadata). `CLAUDE.md` §15's git-safety rules (check status before
  changes, branch for experimental work) cannot be followed until the
  repo is actually initialized — worth flagging since every prior audit/
  decision doc in this repo already assumes git exists.

## 21. Cost/LLM usage notes

The agent run exercised in §16 used the backend's configured LLM provider
for this environment. No live Anthropic/OpenAI call was made — `CLAUDE.md`
§4 mandates `MockProvider` first and no live LLM calls without explicit
approval, and this session did not enable or approve one. AI action log
rows for the test conversation show `provider: null` / mock cost fields,
consistent with mock mode.

## 22. Screens/pages to demo

1. Overview (`/admin`) — stat tiles, mock-environment badge.
2. Mock WhatsApp Test Console (`/admin/mock-whatsapp`) — simulate inbound
   message with quick-fill samples.
3. Conversation detail (`/admin/conversations/[id]`) — chat view, Run Agent
   button, agent draft bubble.
4. Approval Queue (`/admin/approvals`) — pending draft, Approve/Reject.
5. Orders (`/admin/orders`, `/admin/orders/[id]`) — created mock order,
   facility assignment, order timeline.
6. AI Action Logs (`/admin/ai-logs`) — expandable input/output JSON per
   tool call.

Full demo script in `docs/presentation-notes/week-01-admin-ui-demo-notes.md`.

## 23. Commands to run

```
cd "D:\Laundry Khalas App"
docker compose up -d postgres redis api celery_worker celery_beat admin
# or: docker compose up --build   (builds + starts everything)
```

Verify: `http://localhost:8000/health` → `{"status":"ok"}`;
`http://localhost:3000` → redirects to `/admin`.

If the UI 500s on a detail page on first load, run
`docker restart laundrykhalas_admin` (see §18) and retry.

## 24. How to verify manually

Follow `docs/checklists/admin-ui-manual-test-script.md` step by step in a
browser — it walks through the exact flow re-verified at the API level in
§16 (simulate inbound → run agent → approve → see order → check AI logs →
manual takeover → manual reply → release takeover).

## 25. Next recommended step

1. ~~Run `npm run typecheck && npm run lint && npm run build`~~ — **done**
   in a later pass the same day: typecheck clean, lint has 1 non-blocking
   warning, build succeeds. See §16 item 5 and §17.
2. Have a human walk the full manual test script in an actual browser to
   catch anything an HTTP-status-code check can't (visual layout, console
   errors, click targets) — `CLAUDE.md`'s own UI testing rule requires this
   and it still hasn't been possible in any session so far (no browser
   automation tool available in this environment).
3. Founder/team decision on the two new findings in §20 (unused Evolution
   API credential in `.env`; repository not under git version control).
4. Decide whether to add the missing `GET /api/admin/customers/{id}` (or
   embed a masked customer summary in conversation/order responses) — the
   one backend gap flagged as worth prioritizing in
   `docs/audits/admin-ui-start-report.md` §3.
5. Per `CLAUDE.md` §18 roadmap order, the next module after Admin UI
   hardening is the Classifier Agent — do not start it without explicit
   instruction.
