# Build Report — Settings Toggle / Notification Preferences UI Fix

**Date:** 2026-07-20
**Module:** Internal Operations Dashboard → Settings page
**App:** `apps/admin` (Next.js, port 3000)
**Status:** ✅ Fixed, typechecked, production-built, and browser-verified in light + dark + mobile. Mock-only.

---

## 1. Task objective

Fix the visually broken **Notification preferences** card on the Settings page:
toggles misaligned and clipped on the right, labels too close to the switches,
cramped horizontal spacing, inconsistent thumb sizing, and weak dark-mode
contrast. Make the rows clean, aligned, responsive, and premium — and fix the
shared switch component so the same bug is resolved everywhere it appears.

## 2. Root cause

Two shared problems, not a one-off:

1. **Row layout.** Each row was `flex justify-between` with a bare
   `<span className="text-sm text-ink">`. The label had no `min-w-0 flex-1`, so
   long labels could not wrap and instead pushed against / overlapped the
   switch, and on narrow widths this caused right-edge clipping and overflow.
2. **Switch component.** `Switch` accepted no `className`, so a per-row
   `shrink-0` guard could not be applied, and the unchecked track used
   `bg-ink/15`, which is faint and easy to lose in dark mode.

The same row pattern was used by **both** the Notification preferences card and
the Agent settings card, so both were affected — this was a shared-component
bug, fixed once at the component and applied consistently to both cards.

## 3. What was fixed

- Rebuilt the shared `Switch` so it is self-contained, never clips, and stays
  visible in both themes.
- Rebuilt the row structure on both toggle cards to the clean
  label-left / switch-right flex pattern with graceful label wrapping.

## 4. Files modified

- `apps/admin/components/dashboard/ui/Switch.tsx` — shared switch component.
- `apps/admin/app/(dashboard)/settings/page.tsx` — Notification preferences +
  Agent settings cards.

## 5. Files created

- `docs/build-reports/2026-07-20-settings-notification-toggle-fix.md` (this report).

## 6. Component changes — detail

**`Switch.tsx`**

- Now accepts an optional `className` (merged onto the track) so callers can add
  `shrink-0`.
- Track: `inline-flex h-6 w-11 shrink-0 items-center rounded-full` — fixed
  size, vertically centers the thumb, never allowed to shrink.
- Thumb: `h-5 w-5` with `translate-x-0.5` (off) → `translate-x-[1.375rem]` (on),
  keeping it fully inside the 44px track in both states (2px inset each end).
- Checked = `bg-rose` (LaundryKhalas pink); unchecked = `bg-ink/20 dark:bg-ink/25`
  — a neutral gray that stays clearly visible in dark mode.
- Added a subtle accessible focus ring:
  `focus-visible:ring-2 focus-visible:ring-rose/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface`.
- Thumb gets `ring-1 ring-black/5` + `shadow-sm` for definition on white/pink.

**Settings rows (both cards)**

```tsx
<li className="flex items-center justify-between gap-4 py-3">
  <span className="min-w-0 flex-1 text-sm font-medium text-ink">{label}</span>
  <Switch defaultOn={on} label={label} className="shrink-0" />
</li>
```

- `min-w-0 flex-1` on the label → long labels wrap gracefully instead of
  pushing the switch.
- `shrink-0` on the switch → it never shrinks or clips.
- `gap-4` gives clear breathing room between label and switch.
- `py-3` + `divide-y divide-border` → consistent row height and even, clean
  separation. (Cards keep the existing `Panel` `p-5` padding, so nothing reaches
  the right edge.)

No absolute-positioned toggles, no negative margins, no hardcoded right
positioning, no `overflow` clipping were introduced or relied on.

## 7. Before vs after

| | Before | After |
|---|---|---|
| Long labels | Overlapped / pushed the switch | Wrap cleanly, switch untouched |
| Right clipping | Toggles clipped on narrow widths | Always fully visible |
| Row spacing | Cramped, uneven (`py-2`, `space-y-1`) | Even `py-3` rows with dividers |
| Unchecked (dark) | Faint `bg-ink/15`, hard to see | Clear `bg-ink/25` gray |
| Focus | Global outline only | Subtle rose focus ring |
| Reuse | Bug duplicated per card | Fixed in shared `Switch` |

## 8. What is mock-only / live

Purely a presentation fix. The switches remain local UI state (`useState`) on
mock data — no backend, no persistence, no live calls. Consistent with the
Settings page being a mock demonstration surface.

## 9. Tests run

- **Typecheck:** `npm run typecheck` (`tsc --noEmit`) → **exit 0**, no errors.
- **Production build:** `npm run build` → **exit 0**, all 18 routes compiled,
  `/settings` built as static. (One pre-existing ESLint warning in
  `conversations` `useMemo` — unrelated to this change.)
- **Browser verification (Playwright):** captured full-page screenshots of
  `/settings` at desktop (1440px) and mobile (390px) in both light and dark:
  - Toggles fully visible, right-aligned, none clipped.
  - Rows aligned, spacing even.
  - Checked = rose, unchecked = visible gray (incl. dark mode).
  - Mobile: long Agent-settings labels wrap to two lines with the switch still
    fully visible; no horizontal overflow.

## 10. Known limitations / notes

- Playwright logged generic `404 (Not Found)` resource misses (favicon / font
  assets) on the running server. These are **pre-existing and unrelated** to
  this change — the fix adds no new resources — and did not affect rendering.
- The switches are still uncontrolled demo state; wiring to real preferences is
  deferred until a settings backend exists.

## 11. Security / privacy notes

None. UI-only change, no data, no PII, no external calls, no secrets.

## 12. How to verify manually

```bash
cd "apps/admin"
npm run typecheck        # exit 0
npm run build            # exit 0
npm run dev              # then open http://localhost:3000/settings
```

Then on `/settings`: check the **Notification preferences** and **Agent
settings** cards — toggle each switch, toggle dark mode (Theme card), and shrink
the window to mobile width. Toggles should stay aligned, visible, and unclipped
throughout.

## 13. Next recommended step

Wire the Settings toggles (notifications + agent guardrails) to a real
persisted config once a settings backend/table exists, so the guardrail
switches actually gate agent behavior instead of being demo-only.
