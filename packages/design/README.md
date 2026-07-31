# packages/design — shared design system (source, not a package)

Single source of truth for LaundryKhalas dashboard tokens + Tailwind theme.
Consumed by **both** apps via a relative import (no npm workspace, no build step):

- `apps/*/tailwind.config.ts` → `presets: [designPreset]` where
  `import designPreset from "../../packages/design/tailwind-preset"`.
- Tokens are injected into `:root` / `.dark` by the preset's `addBase` plugin — the
  apps' `globals.css` no longer define token variables.

Edit tokens in `tokens.ts`; edit theme scale/shadows/type in `tailwind-preset.ts`.
Never re-add token blocks to an app's `globals.css` (that reintroduces drift).
