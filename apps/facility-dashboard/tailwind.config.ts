import type { Config } from "tailwindcss";

/** Semantic token backed by a CSS variable (R G B triplet) so opacity
 *  utilities work and values swap between light/dark automatically. */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: token("canvas"),
        surface: {
          DEFAULT: token("surface"),
          2: token("surface-2"),
          raised: token("surface-raised"),
        },
        border: {
          DEFAULT: token("border"),
          strong: token("border-strong"),
        },
        ink: {
          DEFAULT: token("ink"),
          muted: token("ink-muted"),
          faint: token("ink-faint"),
        },
        rose: {
          DEFAULT: token("rose"),
          strong: token("rose-strong"),
          contrast: token("rose-contrast"),
        },
        // DEFAULT is the theme-aware token (used by the new dashboard);
        // soft/text are static for backward-compat with legacy /admin pages.
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
      borderRadius: {
        lg: "0.625rem",
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
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
      letterSpacing: {
        eyebrow: "0.12em",
      },
      transitionTimingFunction: {
        "out-quint": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
