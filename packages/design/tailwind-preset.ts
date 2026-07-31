// packages/design/tailwind-preset.ts
// Shared LaundryKhalas design-system preset — the single source of truth for
// both dashboards. Consumed via `presets: [designPreset]` from each app's
// tailwind.config.ts (relative import; no npm workspace, no build step).
//
// Deliberately dependency-free: it imports nothing from `tailwindcss` (this
// folder has no node_modules ancestor, so an import would fail to resolve at
// typecheck/build time). Tailwind accepts a plain function in `plugins`, so we
// inject the CSS-variable tokens via `addBase` without the plugin() wrapper.
import { DARK_TOKENS, LIGHT_TOKENS } from "./tokens";

/** Semantic token backed by a CSS variable (R G B triplet) so opacity
 *  utilities work and values swap between light/dark automatically. */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
const toVars = (t: Record<string, string>): Record<string, string> =>
  Object.fromEntries(Object.entries(t).map(([k, v]) => [`--${k}`, v]));

/** Minimal shape of the Tailwind plugin API surface we use. */
type PluginApi = {
  addBase: (base: Record<string, Record<string, string>>) => void;
  addComponents: (components: Record<string, Record<string, unknown>>) => void;
};

const preset = {
  darkMode: "class" as const,
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
        // Section/module-accent family (wayfinding only — never status colours).
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
        // DEFAULT is the theme-aware token; soft/text are static for backward-compat
        // with legacy /admin pages.
        success: { DEFAULT: token("success"), soft: "#ecfdf5", text: "#065f46" },
        warning: { DEFAULT: token("warning"), soft: "#fffbeb", text: "#92400e" },
        danger: { DEFAULT: token("danger"), soft: "#fef2f2", text: "#991b1b" },
        info: { DEFAULT: token("info"), soft: "#eff6ff", text: "#1e40af" },
        // Legacy-only aliases (old indigo admin) — not used by the new UI.
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
        // Named type scale — hierarchy via weight + spacing, not oversized headings.
        "page-title": ["1.625rem", { lineHeight: "2rem", letterSpacing: "-0.011em" }], // 26px
        section: ["1.1875rem", { lineHeight: "1.6rem", letterSpacing: "-0.006em" }], // 19px
        "card-title": ["0.9375rem", { lineHeight: "1.35rem", letterSpacing: "0" }], // 15px
        "metric-lg": ["1.75rem", { lineHeight: "2rem", letterSpacing: "-0.02em" }], // 28px hero KPI
        metric: ["1.375rem", { lineHeight: "1.6rem", letterSpacing: "-0.012em" }], // 22px KPI
        "metric-sm": ["1.125rem", { lineHeight: "1.4rem", letterSpacing: "-0.006em" }], // 18px
      },
      letterSpacing: { eyebrow: "0.12em" },
      transitionTimingFunction: { "out-quint": "cubic-bezier(0.22, 1, 0.36, 1)" },
    },
  },
  plugins: [
    ({ addBase, addComponents }: PluginApi) => {
      addBase({
        ":root": toVars(LIGHT_TOKENS),
        ".dark": toVars(DARK_TOKENS),
      });
      // Shared interactive-chrome recipe for icon buttons / small controls so
      // hover + focus never drift across apps. Rose focus ring = the one signal.
      addComponents({
        ".lk-control": {
          "@apply inline-flex items-center justify-center rounded-full border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40":
            {},
        },
        ".lk-control--pill": { "@apply h-10 w-10": {} },
      });
    },
  ],
};

export default preset;
