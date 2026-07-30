# Build Report — WhatsApp inbox: filter pills → compact Filter button + popover

**Date:** 2026-07-30

## 1. Build title
Operations → Customer Facing inbox: replace the always-on filter pill wall
("All / Human Needed / Urgent / Active Orders / Resolved") above the conversation
list with **one compact Filter button** beside the "Search chats" input that opens a
grouped, focus-managed **popover** (checkboxes + radios), with live counts, a compact
active-filter summary, and URL-persisted state.

## 2. Task objective
The header above the chat list showed all five filters permanently as pills, eating
vertical space and reducing the number of visible conversations. Required: remove the
pills; add a single funnel Filter button (with an active-count badge + accessible
label) beside Search chats; open a clean anchored popover using existing components;
support the correct multi-select vs radio model derived from the real data; combine
search + filters; indicate active filters compactly; persist filter state to the URL;
keep the three-column layout, chat functionality, colours and spacing untouched.

## 3. What was built
- A new **`InboxFilterMenu`** component: a compact funnel button (`h-9`, rounded-full,
  active-count badge, `aria-label`/`title` "Filter conversations", `aria-haspopup`,
  `aria-expanded`, `aria-controls`) that opens a `role="dialog"` popover anchored under
  it. Popover behaviour mirrors the shell `FilterMenu` pattern: **outside-click close**,
  **Esc close + focus return to the trigger**, focus moved into the panel on open.
- Popover contents, grouped:
  - **Attention** — multi-select **checkboxes** (`role="checkbox"`, `aria-checked`):
    Human Needed, Urgent.
  - **Order status** — single-select **radios** (`role="radiogroup"` / `role="radio"`):
    Active Orders, Resolved (re-clicking the active one clears back to "any").
  - **Clear all** action (shown only when a filter is active); **live counts** on the
    right of every option.
- A **compact active-filter summary** below the search row (only when filters are set):
  a one-row rose chip `Human Needed +1  ×` whose × clears the filters. No pill wall.
- Combined **search + filter** (AND across every active constraint), an **empty state**
  ("No conversations match the selected filters." + **Clear filters** button), and
  **URL persistence** of filter state (`?human_needed=true&urgent=true&order_status=active`).
- **Deselect-on-no-match**: the selected chat is preserved while it still matches and
  safely cleared (with the mobile chat view closed) when a filter/search/status change
  hides it.

## 4. Why it was built
The permanent pill row was cluttered and cost 1–2 conversation rows of vertical space.
A funnel button + popover is the standard compact pattern, keeps the header height
stable, and scales to the two independent filter axes without a wall of chips.

## 5. Files created
- `apps/admin/components/dashboard/whatsapp/InboxFilterMenu.tsx`

## 6. Files modified
- `apps/admin/lib/dashboard/whatsapp-inbox.ts` — added the combined filter model:
  `InboxFilterState`, `OrderStatusFilter`, `emptyFilterState`, `inboxFilterCount`,
  `matchesFilters` (AND predicate), `activeFilterLabels`, and URL (de)serialisers
  `filterStateFromParams` / `writeFilterStateToParams`. The old `matchesFilter` (single
  filter) + `inboxFilters` are **kept** — reused to compute the per-option counts.
- `apps/admin/components/dashboard/whatsapp/WhatsAppChatList.tsx` — removed the pill
  block; put the `InboxFilterMenu` beside the Search input on one row; added the compact
  one-row active-filter summary; empty state now uses `filterActive` and shows a
  "Clear filters" action. Props changed: `filter`/`onFilter` → `filterState`/
  `onFilterChange` + `onClear`.
- `apps/admin/components/dashboard/whatsapp/WhatsAppInbox.tsx` — filter state is now
  **local state (instant source of truth) mirrored to the URL** via two effects
  (URL→state reconcile for back/forward/refresh; state→URL `router.replace`). `visible`
  uses `matchesFilters`; added the deselect-on-no-match effect and a `clearAll` handler.

## 7. Files deleted
None.

## 8. API endpoints added/changed
None. This is a frontend change to an existing client-side inbox surface.

## 9. Database tables/models added/changed
None.

## 10. UI pages/components added/changed
- `InboxFilterMenu` (new); `WhatsAppChatList` + `WhatsAppInbox` (modified). Only the
  Customer Facing → **Inbox** tab is affected; the three-column layout, chat pane,
  context panel, takeover/resolve controls, colours and spacing are unchanged.

## 11. Agent behavior added/changed
None.

## 12. Integrations added/changed
None.

## 13. What is mock-only
The inbox conversations are still the **seeded** dataset (`seedConversations`) that the
whole inbox surface already runs on — the same source the chat, takeover and resolve
actions use. Filtering runs on the **complete** seeded dataset (not a page slice), and
the option counts are computed **dynamically from that real dataset** — not hard-coded.

## 14. What is live
Nothing external. No WhatsApp / Stripe / LLM calls. Filter state is written to the URL
via the Next.js App Router only.

## 15. What is intentionally deferred
- Wiring the inbox to the **live** `GET /api/conversations` backend (a DTO→
  `InboxConversation` mapper + polling/real-time) is a separate, larger migration that
  would also touch chat/takeover/resolve — deliberately **out of scope** here so this
  change stays scoped (per CLAUDE.md §16). The endpoint accepts a `status` query param
  today; the urgent / active-orders axes would be derived client-side (as now) or need
  new server params — noted for that future task.
- No pagination/infinite scroll exists on this list, so none was added; filters already
  operate on the full dataset.

## 16. Tests run
- `npm run typecheck` (tsc --noEmit).
- `npm run lint` (next lint) on the changed files.
- Playwright behavioural run against the live `next dev` on :3000 (desktop 1400×900,
  dark mode, and mobile 390×780), covering the 15 requested cases.
- **No JS unit-test runner is configured in `apps/admin`** (no vitest/jest — only
  `typecheck` + `lint` scripts), so behaviour was verified via typecheck + lint +
  Playwright rather than unit tests. `next build` was **not** run because a dev server
  is up (Windows `next build` collides with a running dev server — documented repo quirk).

## 17. Test results
- **typecheck:** clean (0 errors).
- **lint:** clean (0 warnings/errors) on all four changed files.
- **Playwright (desktop):**
  - Initial list 8 rows, no pills; Filter button present with `aria-label`.
  - Open → `aria-expanded=true`, dialog visible; Esc → closed, focus returned.
  - Human Needed → `?human_needed=true`, 4 rows; **+ Urgent → 1 row** (AND — only Amaan
    is both); badge shows **2**.
  - Clear all → empty URL, 8 rows.
  - Active Orders → `?order_status=active`, 5 rows; **Resolved → 1 row, Active
    auto-unchecked** (radio mutual exclusivity).
  - Resolved + search "Mariam" → 1; Resolved + "Amaan" → **0 with empty state**
    ("No conversations match the selected filters." + Clear filters button).
  - Refresh with `?human_needed=true&urgent=true` → badge 2, 1 row (**survives refresh**).
  - Browser **back** navigates without breaking.
  - **Deselect-on-no-match:** selecting Amaan then filtering to Resolved deselects Amaan
    and shows the "Select a conversation" placeholder.
- **Dark mode:** popover uses the dark raised surface (not bright white), rose accent on
  checked checkbox/radio, counts intact.
- **Mobile (390px):** Filter button collapses to icon-only; popover bounding box fully
  within the viewport (right edge 373 ≤ 390) — no overflow.

## 18. Bugs/issues found (and fixed during the build)
1. **Async-router race** — a first pass derived filter state *purely* from the URL and
   wrote every toggle with `router.push`. Rapid successive toggles read a **stale**
   `useSearchParams()` snapshot and clobbered each other (a second click dropped the
   first). Fixed by making **local React state the instant source of truth** and
   mirroring it to the URL with two guarded effects (URL→state reconcile; state→URL
   `router.replace` reading `window.location` at write time to avoid a ping-pong with
   the reconcile effect). Re-tested: multi-toggle is reliable.

## 19. Known limitations
- Inbox data is seeded, not live (see §13/§15).
- Filter state persists in the URL; **search text stays local** (matches the rest of the
  dashboard, where only `?tab=` is URL-bound) — search is intentionally not shareable.
- `router.replace` is used for filter writes, so **back returns to the previous page**
  rather than stepping through each individual toggle (chosen to avoid a history entry
  per checkbox click); refresh + shareable URL + back/forward-into-the-page all work.

## 20. Security/privacy notes
No PII in the URL — only booleans/enums (`human_needed`, `urgent`, `order_status`).
Phones remain masked in the list (unchanged). No new network calls or data flows.

## 21. Cost/LLM usage notes
None — no LLM calls.

## 22. Screens/pages to demo
- `/operations/customer-facing` (Inbox tab): the header now reads
  `[ Search chats ] [ Filter ]` — no pill wall.
- Open Filter → grouped popover (Attention checkboxes / Order status radios) with counts.
- Select Human Needed + Urgent → badge "2", one-row summary chip "Human Needed +1 ×",
  list narrows to the matching conversation.
- Search "Mariam" + Resolved → single match; "Amaan" + Resolved → empty state + Clear.
- Toggle dark mode; resize to mobile (icon-only button, in-viewport popover).

## 23. Commands to run
```
cd apps/admin
npm run typecheck
npm run lint
npm run dev            # http://localhost:3000  → /operations/customer-facing
```

## 24. How to verify manually
1. Open http://localhost:3000/operations/customer-facing (Inbox tab).
2. Confirm the pills are gone and a compact **Filter** button sits beside Search chats.
3. Click Filter → popover opens with Attention (checkboxes) + Order status (radios) and
   live counts. Tick Human Needed and Urgent → list narrows (AND), badge shows 2, a
   one-row summary chip appears below the search.
4. Open again → Active Orders then Resolved: only one stays selected (radio).
5. Type a name in Search with a filter on → results are the intersection; a non-matching
   combination shows "No conversations match the selected filters." + Clear filters.
6. Refresh the page → filters persist (URL query params). Press browser Back → no break.
7. Select a chat, then apply a filter it doesn't match → it deselects safely.
8. Press Esc to close (focus returns to the button); toggle dark mode; resize to mobile.

## 25. Next recommended step
Wire the inbox list + counts to the live `GET /api/conversations` backend (DTO mapper +
polling/real-time) behind this same filter UI, passing `status` server-side and deriving
the urgent / active-orders axes, so the filter operates on live conversations at scale.
```
```
