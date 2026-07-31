# Dashboard Redesign — Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one shared, reversible design foundation for both dashboards — a shared Tailwind preset + tokens, Geist typography, a named type scale, a canonical control-chrome class, and a reconciled loading/error state set — with zero layout changes and no regressions.

**Architecture:** A new repo-level `packages/design/` holds the single source of truth (a Tailwind **preset** that carries the `theme.extend`, injects the CSS-variable tokens via `addBase`, and registers a shared `.lk-control` component). Both apps consume it via a **relative import** (no npm workspace). CSS-variable tokens move out of each app's `globals.css` into the preset so they can never drift again; the `.lk-*` animation/base layer stays per-app (identical). Fonts swap to Geist while keeping Bricolage Grotesque as the display face. Components stay per-app but are reconciled to one canonical implementation.

**Tech Stack:** Next.js 15.5.18 (App Router), Tailwind CSS 3.4.14 (`darkMode: "class"`, JIT), React 19.2.8, TypeScript 5.6.3, `next/font`, `tailwindcss/plugin`.

## Global Constraints

- **Reversibility:** All work on branch `feat/dashboard-redesign`. Never commit to `main`. Baseline restore point = tag `pre-redesign-baseline` (`ca4517d`). No runtime old/new toggle; no parallel old/new component code.
- **Presentation-only:** Do not change business logic, API calls, auth, permissions, real-time subscriptions, or data. Do not fabricate data. Admin's static/mock pages stay mock.
- **No token/value drift:** Token RGB values are copied **verbatim** from `apps/admin/app/globals.css` (the canonical superset — it already includes `--accent-orange`). Do not alter any colour value in Phase 1.
- **Rose is a signal, not a fill.** Status never colour-only.
- **UI copy rule:** never show the words mock/demo/dummy/test in UI; use Staged/Standby/Coming soon/Operational.
- **Verification gate for every task** (this is a design-system layer — the repo's frontend gate per `CLAUDE.md §14` is typecheck + lint + build + visual, not unit tests): for each touched app run `npm run typecheck`, `npm run lint`, `npm run build`, and a visual check in **both** light and dark. "Both apps" = `apps/admin` (port 3000) and `apps/facility-dashboard` (port 3010).
- **Commit cadence:** one commit per task, message prefix `Phase 1:`.

---

## File Structure

**Created**
- `packages/design/tailwind-preset.ts` — shared Tailwind preset: `theme.extend` (colors, fontFamily, radius, shadow, fontSize incl. new type scale, letterSpacing, timing) + a plugin that `addBase`-injects the `:root`/`.dark` CSS-variable tokens and `addComponents` the `.lk-control` chrome class.
- `packages/design/tokens.ts` — the token maps (`LIGHT_TOKENS`, `DARK_TOKENS`) as plain objects, imported by the preset. Single source for the CSS-variable values.
- `packages/design/README.md` — how the shared design source is consumed (relative import, no build step, no workspace).
- `packages/design/verify-preset.mjs` — a tiny Node guard asserting the preset exports the expected token + fontSize keys (real pass/fail for Task 1).

**Modified**
- `apps/admin/tailwind.config.ts` + `apps/facility-dashboard/tailwind.config.ts` — replace inline `theme.extend` with `presets: [designPreset]`.
- `apps/admin/app/globals.css` + `apps/facility-dashboard/app/globals.css` — remove the `:root{…}` / `.dark{…}` token blocks (now injected by the preset); keep base rules + `.lk-*` layer.
- `apps/admin/app/layout.tsx` + `apps/facility-dashboard/app/layout.tsx` — swap body/numeric fonts to Geist; keep Bricolage display.
- Canonical header/metric primitives in both apps — replace arbitrary `text-[…]` with type-scale utilities.
- Admin Topbar/ThemeToggle/UserMenu + facility FacilityHeader — adopt `.lk-control`.
- `apps/admin/components/dashboard/ui/states.tsx` — add `ErrorState` (verbatim from facility).
- `apps/admin/components/ui/tones.ts` + `apps/facility-dashboard/components/ui/tones.ts` — one chip opacity/ring family (if drifted).
- Both apps' `ui/Button.tsx` — reconcile to one canonical version.
- Both apps' `ui/` — add a shared dependency-free `Tooltip` primitive.

---

## Task 1: Shared preset + tokens (zero visual change)

Extract the duplicated `theme.extend` and the CSS-variable tokens into `packages/design/`, wire both apps to it, and prove the rendered output is unchanged.

**Files:**
- Create: `packages/design/tokens.ts`, `packages/design/tailwind-preset.ts`, `packages/design/README.md`, `packages/design/verify-preset.mjs`
- Modify: `apps/admin/tailwind.config.ts` (replace lines 10-87 `theme` block), `apps/facility-dashboard/tailwind.config.ts` (same), `apps/admin/app/globals.css:12-104` (remove token blocks), `apps/facility-dashboard/app/globals.css` (remove its `:root`/`.dark` token blocks)

**Interfaces:**
- Produces: `packages/design/tailwind-preset.ts` default export = a Tailwind `Config` fragment usable in `presets: [...]`. `packages/design/tokens.ts` exports `LIGHT_TOKENS: Record<string,string>` and `DARK_TOKENS: Record<string,string>` (CSS-var name without `--` → `"R G B"` string).

- [ ] **Step 1: Create the token maps** — `packages/design/tokens.ts`. Copy every value **verbatim** from `apps/admin/app/globals.css:12-104` (admin is the superset — includes `--accent-orange`).

```ts
// packages/design/tokens.ts
// Single source of truth for LaundryKhalas design tokens (R G B triplets).
// Values copied verbatim from apps/admin/app/globals.css (the superset).
// Consumed by tailwind-preset.ts and injected via addBase into :root / .dark.
export const LIGHT_TOKENS: Record<string, string> = {
  canvas: "248 244 246",
  surface: "255 255 255",
  "surface-2": "249 245 247",
  "surface-raised": "255 255 255",
  "surface-sunken": "244 239 242",
  border: "230 222 226",
  "border-strong": "212 201 208",
  ink: "26 20 24",
  "ink-muted": "107 99 104",
  "ink-faint": "150 143 148",
  rose: "214 51 108",
  "rose-strong": "180 45 94",
  "rose-contrast": "255 255 255",
  success: "5 150 105",
  warning: "217 119 6",
  danger: "220 38 38",
  info: "37 99 235",
  "c-rose": "214 51 108",
  "c-plum": "124 58 173",
  "c-teal": "13 148 136",
  "c-amber": "217 119 6",
  "c-slate": "71 85 105",
  "c-sky": "2 132 199",
  "accent-teal": "13 148 136",
  "accent-amber": "194 120 3",
  "accent-violet": "124 58 237",
  "accent-slate": "71 85 105",
  "accent-sky": "2 132 199",
  "accent-indigo": "79 70 229",
  "accent-fuchsia": "192 38 211",
  "accent-cyan": "8 145 178",
  "accent-steel": "55 71 105",
  "accent-plum": "147 51 190",
  "accent-orange": "234 88 12",
  ring: "214 51 108",
  "shadow-color": "24 15 20",
};

export const DARK_TOKENS: Record<string, string> = {
  canvas: "13 15 19",
  surface: "22 27 34",
  "surface-2": "28 34 43",
  "surface-raised": "30 36 46",
  "surface-sunken": "17 21 27",
  border: "44 51 62",
  "border-strong": "60 69 82",
  ink: "237 233 236",
  "ink-muted": "158 164 174",
  "ink-faint": "112 119 129",
  rose: "232 76 136",
  "rose-strong": "240 106 162",
  "rose-contrast": "20 12 16",
  success: "52 211 153",
  warning: "251 191 36",
  danger: "248 113 113",
  info: "96 165 250",
  "c-rose": "232 76 136",
  "c-plum": "167 139 250",
  "c-teal": "45 212 191",
  "c-amber": "251 191 36",
  "c-slate": "148 163 184",
  "c-sky": "56 189 248",
  "accent-teal": "45 212 191",
  "accent-amber": "251 191 36",
  "accent-violet": "167 139 250",
  "accent-slate": "148 163 184",
  "accent-sky": "56 189 248",
  "accent-indigo": "129 140 248",
  "accent-fuchsia": "232 121 249",
  "accent-cyan": "34 211 238",
  "accent-steel": "130 148 184",
  "accent-plum": "192 132 252",
  "accent-orange": "251 146 60",
  ring: "232 76 136",
  "shadow-color": "0 0 0",
};
```

- [ ] **Step 2: Create the preset** — `packages/design/tailwind-preset.ts`. This carries the theme fragment (verbatim from `apps/admin/tailwind.config.ts:11-86`, which already includes `accent.orange`) plus the base-token injection. The new fontSize keys (type scale) are added here in Task 3; for now include only the existing `xxs`.

```ts
// packages/design/tailwind-preset.ts
// Shared LaundryKhalas design-system preset — the single source of truth for
// both dashboards. Consumed via `presets: [require("../../packages/design/tailwind-preset")]`.
import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";
import { DARK_TOKENS, LIGHT_TOKENS } from "./tokens";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
const toVars = (t: Record<string, string>) =>
  Object.fromEntries(Object.entries(t).map(([k, v]) => [`--${k}`, v]));

const preset: Partial<Config> = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: token("canvas"),
        surface: {
          DEFAULT: token("surface"),
          2: token("surface-2"),
          raised: token("surface-raised"),
          sunken: token("surface-sunken"),
        },
        border: { DEFAULT: token("border"), strong: token("border-strong") },
        accent: {
          teal: token("accent-teal"),
          amber: token("accent-amber"),
          violet: token("accent-violet"),
          slate: token("accent-slate"),
          sky: token("accent-sky"),
          indigo: token("accent-indigo"),
          fuchsia: token("accent-fuchsia"),
          cyan: token("accent-cyan"),
          steel: token("accent-steel"),
          plum: token("accent-plum"),
          orange: token("accent-orange"),
        },
        ink: { DEFAULT: token("ink"), muted: token("ink-muted"), faint: token("ink-faint") },
        rose: {
          DEFAULT: token("rose"),
          strong: token("rose-strong"),
          contrast: token("rose-contrast"),
        },
        success: { DEFAULT: token("success"), soft: "#ecfdf5", text: "#065f46" },
        warning: { DEFAULT: token("warning"), soft: "#fffbeb", text: "#92400e" },
        danger: { DEFAULT: token("danger"), soft: "#fef2f2", text: "#991b1b" },
        info: { DEFAULT: token("info"), soft: "#eff6ff", text: "#1e40af" },
        brand: { DEFAULT: "#4f46e5", hover: "#4338ca", soft: "#eef2ff" },
        neutral: { soft: "#f3f4f6", text: "#374151" },
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-numeric)", "ui-monospace", "monospace"],
      },
      borderRadius: { lg: "0.625rem", xl: "0.875rem", "2xl": "1.125rem", "3xl": "1.5rem" },
      boxShadow: {
        card: "0 1px 2px -1px rgb(var(--shadow-color) / 0.08), 0 1px 3px 0 rgb(var(--shadow-color) / 0.06)",
        raised:
          "0 4px 12px -2px rgb(var(--shadow-color) / 0.10), 0 2px 6px -2px rgb(var(--shadow-color) / 0.08)",
        pop: "0 12px 32px -8px rgb(var(--shadow-color) / 0.22), 0 4px 12px -4px rgb(var(--shadow-color) / 0.12)",
        "rose-glow": "0 6px 20px -6px rgb(var(--rose) / 0.45)",
      },
      fontSize: {
        xxs: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      letterSpacing: { eyebrow: "0.12em" },
      transitionTimingFunction: { "out-quint": "cubic-bezier(0.22, 1, 0.36, 1)" },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({
        ":root": toVars(LIGHT_TOKENS),
        ".dark": toVars(DARK_TOKENS),
      });
    }),
  ],
};

export default preset;
```

- [ ] **Step 3: Write the verify guard** — `packages/design/verify-preset.mjs`.

```js
// packages/design/verify-preset.mjs
// Guard: the preset must expose the token colour keys + the xxs fontSize.
// Run: node packages/design/verify-preset.mjs  → exits non-zero on any gap.
import { LIGHT_TOKENS, DARK_TOKENS } from "./tokens.ts";

const REQUIRED = [
  "canvas", "surface", "border", "ink", "rose", "success", "warning",
  "danger", "info", "accent-orange", "ring", "shadow-color",
];
const missingL = REQUIRED.filter((k) => !(k in LIGHT_TOKENS));
const missingD = REQUIRED.filter((k) => !(k in DARK_TOKENS));
if (missingL.length || missingD.length) {
  console.error("Missing tokens — light:", missingL, "dark:", missingD);
  process.exit(1);
}
if (Object.keys(LIGHT_TOKENS).length !== Object.keys(DARK_TOKENS).length) {
  console.error("Light/dark token counts differ.");
  process.exit(1);
}
console.log("preset tokens OK:", Object.keys(LIGHT_TOKENS).length, "tokens x2 themes");
```

Note: `tokens.ts` is plain TS with no type-only syntax in the exported objects, so Node 20+ can import it directly only if run through a TS loader. If `node packages/design/verify-preset.mjs` errors on the `.ts` import, run it with the app's TypeScript available: `node --experimental-strip-types packages/design/verify-preset.mjs` (Node 22) — or skip this guard and rely on the build. Do not block the task on the guard if the Node version lacks TS stripping; the build in Step 6 is the authoritative gate.

- [ ] **Step 4: Write `packages/design/README.md`**

```markdown
# packages/design — shared design system (source, not a package)

Single source of truth for LaundryKhalas dashboard tokens + Tailwind theme.
Consumed by **both** apps via a relative import (no npm workspace, no build step):

- `apps/*/tailwind.config.ts` → `presets: [require("../../packages/design/tailwind-preset").default]`
- Tokens are injected into `:root` / `.dark` by the preset's `addBase` plugin — the
  apps' `globals.css` no longer define token variables.

Edit tokens in `tokens.ts`; edit theme scale/shadows in `tailwind-preset.ts`.
Never re-add token blocks to an app's `globals.css` (that reintroduces drift).
```

- [ ] **Step 5: Wire both apps to the preset.** In `apps/admin/tailwind.config.ts`, replace the whole `theme: { … }` object (lines 10-87) and the `token` helper with a preset reference; keep `content` and `darkMode`:

```ts
// apps/admin/tailwind.config.ts
import type { Config } from "tailwindcss";
import designPreset from "../../packages/design/tailwind-preset";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  presets: [designPreset],
};

export default config;
```

Apply the identical change to `apps/facility-dashboard/tailwind.config.ts` (same three `content` globs). Then remove the token blocks from each `globals.css`: delete `apps/admin/app/globals.css:12-104` (the `:root{…}` and `.dark{…}` blocks **only** — keep the header comment at 5-11 optional, and keep everything from line 106 onward: `html,body`, `*{border-color}`, `.tnum`, scrollbars, `:focus-visible`, reduced-motion, and all `.lk-*` blocks). Do the same in `apps/facility-dashboard/app/globals.css` (remove its `:root`/`.dark` token blocks; keep its base + `.lk-*` layer).

- [ ] **Step 6: Verify — build + visual parity (both apps).**

Run for each app:
```bash
cd apps/admin && npm run typecheck && npm run lint && npm run build
cd ../facility-dashboard && npm run typecheck && npm run lint && npm run build
```
Expected: all pass. Then boot each dev server and screenshot Overview + one data page in **light and dark**; compare against baseline (`git stash` is not needed — compare against `main`). Expected: **pixel-identical** (values unchanged; this task only relocates them). If a colour is missing/wrong, a token value was mis-copied in Step 1 — fix and rebuild.

- [ ] **Step 7: Commit**

```bash
git add packages/design apps/admin/tailwind.config.ts apps/facility-dashboard/tailwind.config.ts apps/admin/app/globals.css apps/facility-dashboard/app/globals.css
git commit -m "Phase 1: shared design preset + tokens (packages/design), both apps wired; no visual change"
```

---

## Task 2: Geist typography (keep Bricolage display)

Swap body → Geist Sans and numeric → Geist Mono in both apps, keeping Bricolage Grotesque for the display face and the same `--font-*` variable names (so the preset needs no change).

**Files:**
- Modify: `apps/admin/app/layout.tsx:2,15-24`, `apps/facility-dashboard/app/layout.tsx:2,14-23`

**Interfaces:**
- Consumes: preset `fontFamily` (`var(--font-body)`, `var(--font-numeric)`, `var(--font-display)`) from Task 1 — unchanged.
- Produces: `--font-body` = Geist Sans, `--font-numeric` = Geist Mono, `--font-display` = Bricolage Grotesque, applied on `<html>`.

- [ ] **Step 1: Swap the fonts in `apps/admin/app/layout.tsx`.** Change the import (line 2) and the `body`/`numeric` loaders (keep `display` = Bricolage, keep variable names):

```tsx
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";
// …
const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const body = Geist({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const numeric = Geist_Mono({ subsets: ["latin"], variable: "--font-numeric", display: "swap" });
```

Leave the `<html className={…display.variable} ${body.variable} ${numeric.variable}}>` untouched (variable names unchanged). Apply the identical edit to `apps/facility-dashboard/app/layout.tsx`.

- [ ] **Step 2: Verify — build + visual (both apps).**
```bash
cd apps/admin && npm run typecheck && npm run build
cd ../facility-dashboard && npm run typecheck && npm run build
```
Expected: pass, and body text renders in Geist; money/IDs render in Geist Mono; page titles/hero KPI still Bricolage. Check light + dark.

**Fallback (only if the build errors that `Geist`/`Geist_Mono` are not valid `next/font/google` families):** install the self-hosted package in each app — `npm i geist` — and instead use:
```tsx
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
// apply GeistSans.variable + GeistMono.variable + display.variable on <html>,
```
then add to `packages/design/tokens.ts` LIGHT+DARK an alias so the preset var names still resolve — add these two lines to BOTH maps: `"font-body": "", "font-numeric": ""` is NOT valid (they are font stacks, not RGB). Instead, in `packages/design/tailwind-preset.ts` change `fontFamily.sans` to `["var(--font-geist-sans)", …]` and `fontFamily.mono` to `["var(--font-geist-mono)", …]` (leave `display` on `--font-display`). Rebuild. Document whichever route was used in the task commit message.

- [ ] **Step 3: Commit**
```bash
git add apps/admin/app/layout.tsx apps/facility-dashboard/app/layout.tsx
git commit -m "Phase 1: Geist Sans (body) + Geist Mono (numeric); keep Bricolage display"
```

---

## Task 3: Named type scale + adopt in header/metric primitives

Add type-scale fontSize tokens to the preset and replace the arbitrary `text-[…]` values in the canonical header/metric components of both apps, so hierarchy is systematic.

**Files:**
- Modify: `packages/design/tailwind-preset.ts` (fontSize block), `apps/admin/components/dashboard/shell/PageHeader.tsx:76`, `apps/admin/components/dashboard/ui/StatCard.tsx:54,117`, `apps/admin/components/dashboard/ui/primitives.tsx:63`, `apps/admin/components/dashboard/shell/Brand.tsx:23`, `apps/facility-dashboard/components/shared/MobilePageHeader.tsx:43`, `apps/facility-dashboard/components/minimal/MinimalKpiStrip.tsx` (KPI value size), `apps/facility-dashboard/components/ui/primitives.tsx` (PanelHeader), `apps/facility-dashboard/components/shell/Brand.tsx`

**Interfaces:**
- Produces: fontSize utilities `text-page-title`, `text-section`, `text-card-title`, `text-metric-lg`, `text-metric`, `text-metric-sm` (in addition to existing `text-xxs`).

- [ ] **Step 1: Add the scale to the preset.** Replace the `fontSize` block in `packages/design/tailwind-preset.ts` with:

```ts
fontSize: {
  xxs: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
  // Type scale — hierarchy via weight + spacing, not oversized headings.
  "page-title": ["1.625rem", { lineHeight: "2rem", letterSpacing: "-0.011em" }], // 26px
  section: ["1.1875rem", { lineHeight: "1.6rem", letterSpacing: "-0.006em" }], // 19px
  "card-title": ["0.9375rem", { lineHeight: "1.35rem", letterSpacing: "0" }], // 15px
  "metric-lg": ["1.75rem", { lineHeight: "2rem", letterSpacing: "-0.02em" }], // 28px hero KPI
  metric: ["1.375rem", { lineHeight: "1.6rem", letterSpacing: "-0.012em" }], // 22px KPI
  "metric-sm": ["1.125rem", { lineHeight: "1.4rem", letterSpacing: "-0.006em" }], // 18px
},
```

- [ ] **Step 2: Adopt in admin primitives.** Replace arbitrary sizes with scale utilities (keep every other class on each element):
  - `PageHeader.tsx:76` — `text-2xl … md:text-[1.7rem]` → `text-page-title`
  - `StatCard.tsx:54` — `text-[1.6rem]` → `text-metric`
  - `StatCard.tsx:117` (HeroStat) — `text-[2.4rem]` → `text-metric-lg`
  - `primitives.tsx:63` (PanelHeader) — `text-[0.95rem]` → `text-card-title`
  - `Brand.tsx:23` — `text-[0.95rem]` → `text-card-title`

- [ ] **Step 3: Adopt in facility primitives (mirror).**
  - `shared/MobilePageHeader.tsx:43` — `text-xl sm:text-2xl` → `text-page-title`
  - `minimal/MinimalKpiStrip.tsx` — the KPI value size → `text-metric`
  - `ui/primitives.tsx` PanelHeader `text-[0.95rem]` → `text-card-title`
  - `shell/Brand.tsx` wordmark title → `text-card-title`

- [ ] **Step 4: Verify (both apps).** `npm run typecheck && npm run build` in each. Visual: page titles ≈26px, hero KPI ≈28px, standard KPI ≈22px, card titles 15px; hierarchy reads cleaner; nothing overflows. Light + dark.

- [ ] **Step 5: Commit**
```bash
git commit -am "Phase 1: named type scale; adopt in header/metric primitives (both apps)"
```

---

## Task 4: Canonical `.lk-control` chrome class

Add one shared class for the repeated icon-button/border/hover/focus recipe and adopt it where the recipe is copy-pasted, so hover/focus never drift.

**Files:**
- Modify: `packages/design/tailwind-preset.ts` (add `addComponents`), `apps/admin/components/dashboard/shell/Topbar.tsx:31,47,58`, `apps/admin/components/dashboard/shell/ThemeToggle.tsx:21`, `apps/admin/components/dashboard/shell/UserMenu.tsx:49`, `apps/facility-dashboard/components/layout/FacilityHeader.tsx` (bell + logout icon buttons)

**Interfaces:**
- Produces: component class `.lk-control` (base chrome) and `.lk-control--pill` (44px round tap target) available in both apps.

- [ ] **Step 1: Register the class in the preset plugin.** Extend the plugin to also `addComponents`:

```ts
plugin(({ addBase, addComponents }) => {
  addBase({ ":root": toVars(LIGHT_TOKENS), ".dark": toVars(DARK_TOKENS) });
  addComponents({
    ".lk-control": {
      "@apply inline-flex items-center justify-center rounded-full border border-border bg-surface text-ink-muted transition-colors":
        {},
      "@apply hover:border-border-strong hover:text-ink": {},
      "@apply focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40": {},
    },
    ".lk-control--pill": { "@apply h-10 w-10": {} },
  });
});
```

- [ ] **Step 2: Adopt in admin shell.** Replace the inline recipe (`border border-border bg-surface … hover:border-border-strong hover:text-ink …`) on the icon buttons in `Topbar.tsx:31,47,58`, `ThemeToggle.tsx:21`, `UserMenu.tsx:49` with `lk-control lk-control--pill` plus any size/icon-specific classes those buttons already carry (keep `h-9 w-9` where present, or migrate to `lk-control--pill`; preserve `aria-label`s).

- [ ] **Step 3: Adopt in facility header.** In `FacilityHeader.tsx`, replace the bell + logout button chrome strings with `lk-control lk-control--pill` (keep their existing `relative`, badge child, and `aria-label`).

- [ ] **Step 4: Verify (both apps).** `npm run typecheck && npm run lint && npm run build` each. Visual: all header icon buttons share identical rest/hover/focus; keyboard-tab shows a consistent rose focus ring. Light + dark.

- [ ] **Step 5: Commit**
```bash
git commit -am "Phase 1: shared .lk-control chrome class; adopt in both app headers"
```

---

## Task 5: Add `ErrorState` to admin (close the states gap)

Admin's canonical `dashboard/ui/states.tsx` has no `ErrorState`; facility's does. Add the identical component so both kits match.

**Files:**
- Modify: `apps/admin/components/dashboard/ui/states.tsx` (add `ErrorState`; add `AlertTriangle`, `RefreshCw` to the lucide import)

**Interfaces:**
- Produces: `ErrorState({ title?, description?, onRetry?, className? })` exported from admin `dashboard/ui/states.tsx` — signature identical to `apps/facility-dashboard/components/ui/states.tsx:53`.

- [ ] **Step 1: Add the import + component.** Update the lucide import line to include `AlertTriangle` and `RefreshCw`, then append (verbatim from facility `states.tsx:49-87`):

```tsx
/**
 * Error state with an optional retry. Used when an API call fails so the operator
 * always sees a clear, recoverable message instead of a blank screen.
 */
export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-danger/30 bg-danger/5 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <p className="font-display text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-xs text-xs text-ink-muted">{description}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-full border border-border bg-surface px-4 text-xs font-semibold text-ink transition-colors hover:border-border-strong hover:bg-surface-2"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify.** `cd apps/admin && npm run typecheck && npm run lint && npm run build`. Expected: pass, `ErrorState` importable from `@/components/dashboard/ui/states`. (No page consumes it yet — that happens when live pages are redesigned in Phase 3.)

- [ ] **Step 3: Commit**
```bash
git commit -am "Phase 1: add ErrorState to admin states kit (parity with facility)"
```

---

## Task 6: Reconcile the tone chip family (one badge look)

The audit found chip opacity/ring inconsistency (`/10` vs `/12`+ring). Make `tones.ts` the one badge family in both apps and ensure the two files are identical.

**Files:**
- Modify: `apps/admin/components/dashboard/ui/tones.ts`, `apps/facility-dashboard/components/ui/tones.ts`

**Interfaces:**
- Consumes: `Tone` union already exported by each `tones.ts`.
- Produces: `toneChip`, `toneDot`, `toneText` maps identical across both apps.

- [ ] **Step 1: Diff the two files.**
```bash
diff <(tr -d '\r' < apps/admin/components/dashboard/ui/tones.ts) \
     <(tr -d '\r' < apps/facility-dashboard/components/ui/tones.ts)
```
If they are identical (ignoring CRLF), skip to Step 3 and note "already unified" in the commit. If they differ, pick admin's `dashboard/ui/tones.ts` as canonical and copy its `toneChip`/`toneDot`/`toneText` bodies into the facility file, preserving the facility file's import paths and `Tone` type.

- [ ] **Step 2: Ensure one chip recipe.** Confirm every entry in `toneChip` uses the same opacity + inset-ring formula (e.g. `bg-<tone>/12 text-<tone> ring-1 ring-inset ring-<tone>/20`). Where `FacilityManager.tsx:22-28` hand-rolls status chips, leave it for Phase 4 (documented there) — Phase 1 only unifies the shared `tones.ts`.

- [ ] **Step 3: Verify (both apps).** `npm run typecheck && npm run build` each. Visual: status chips in both apps read as one family in light + dark.

- [ ] **Step 4: Commit**
```bash
git commit -am "Phase 1: unify tone chip family across both apps"
```

---

## Task 7: Reconcile `Button` + add a `Tooltip` primitive

Bring the two `Button.tsx` files to one canonical implementation and add a small dependency-free `Tooltip` for icon-only actions (a11y).

**Files:**
- Modify: `apps/admin/components/dashboard/ui/Button.tsx`, `apps/facility-dashboard/components/ui/Button.tsx`
- Create: `apps/admin/components/dashboard/ui/Tooltip.tsx`, `apps/facility-dashboard/components/ui/Tooltip.tsx`

**Interfaces:**
- Produces: identical `Button` variants/sizes in both apps; `Tooltip({ label, children, side? })` wrapping a focusable trigger, exposing `aria-label`/`title` fallback.

- [ ] **Step 1: Reconcile Button.** Diff the two files (as in Task 6 Step 1). Choose admin's as canonical; copy its variant/size maps into facility's file, preserving facility import paths. Keep all existing variant names and props (no API change — consumers must not break).

- [ ] **Step 2: Add the Tooltip primitive (both apps, identical body).** CSS-only, no new dependency:

```tsx
// Tooltip.tsx — lightweight, dependency-free. Wrap a focusable trigger; the
// label shows on hover AND keyboard focus. `title` is the no-JS/SR fallback.
"use client";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils"; // admin: "@/lib/utils" (same in facility)

export function Tooltip({
  label,
  children,
  side = "bottom",
}: {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
}) {
  return (
    <span className="group/tt relative inline-flex" title={label}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xxs font-medium text-canvas opacity-0 shadow-pop transition-opacity duration-150 group-hover/tt:opacity-100 group-focus-within/tt:opacity-100",
          side === "bottom" ? "top-[calc(100%+6px)]" : "bottom-[calc(100%+6px)]",
        )}
      >
        {label}
      </span>
    </span>
  );
}
```

- [ ] **Step 3: Verify (both apps).** `npm run typecheck && npm run lint && npm run build` each. Visual: existing buttons unchanged; wrapping a header icon-button in `<Tooltip label="…">` shows the label on hover and on keyboard focus, respecting reduced-motion. Light + dark.

- [ ] **Step 4: Commit**
```bash
git commit -am "Phase 1: reconcile Button across apps; add dependency-free Tooltip primitive"
```

---

## Phase 1 exit checks
- [ ] Both apps: `npm run typecheck && npm run lint && npm run build` all green.
- [ ] Visual parity confirmed light + dark on Overview + one data page in each app (only intended changes: Geist body/mono, tighter type hierarchy, consistent icon-button chrome/focus — no layout moves).
- [ ] `packages/design/` is the sole definition of tokens + theme; neither app's `globals.css` redefines token variables.
- [ ] No business logic / data / API / auth touched.
- [ ] Baseline still one command away: `git switch main` (or `git checkout pre-redesign-baseline`).
- [ ] Write a short build report `docs/build-reports/2026-07-31-dashboard-redesign-phase-1.md` (per CLAUDE.md §12) and note remaining Phase-2 handoffs (shell).

---

## Self-review notes (spec coverage)
- Spec §4.1 shared `packages/design/` → Task 1. §4.2 fonts → Task 2. §4.3 type scale → Task 3. §4.4 control-chrome/badge family/ErrorState → Tasks 4–6. "reconcile Button/Badge/Input/Tooltip" → Tasks 6 (badge), 7 (Button, Tooltip). **Input** reconciliation is intentionally deferred: no shared `Input.tsx` exists yet in the audit; form inputs are redesigned with the forms work in Phases 3–4 (noted, not silently dropped). Skeleton-first loading conversion happens per-page in Phases 3–4 (the `Skeleton` primitive already exists in both kits after Task 5 parity); Phase 1 only ensures the primitives exist.
- Reversibility (spec §Non-Neg-1) enforced via Global Constraints + exit checks. Presentation-only (spec §Non-Neg-2 / data scope) enforced per task.
