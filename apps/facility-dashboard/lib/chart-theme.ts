/** Chart colors reference CSS variables, so every chart recolors instantly
 *  when the theme toggles — no re-render or JS theme lookups needed. */
export const CHART = {
  rose: "rgb(var(--c-rose))",
  plum: "rgb(var(--c-plum))",
  teal: "rgb(var(--c-teal))",
  amber: "rgb(var(--c-amber))",
  slate: "rgb(var(--c-slate))",
  sky: "rgb(var(--c-sky))",
  grid: "rgb(var(--border) / 0.7)",
  axis: "rgb(var(--ink-faint))",
  success: "rgb(var(--success))",
  danger: "rgb(var(--danger))",
} as const;

/** Ordered categorical sequence — rose leads, then well-separated hues. */
export const CATEGORICAL = [
  CHART.rose,
  CHART.plum,
  CHART.teal,
  CHART.amber,
  CHART.sky,
  CHART.slate,
];

/** Shared tooltip style so every chart tooltip matches the surface system. */
export const tooltipStyle = {
  backgroundColor: "rgb(var(--surface-raised))",
  border: "1px solid rgb(var(--border-strong))",
  borderRadius: "0.75rem",
  boxShadow: "0 12px 32px -8px rgb(var(--shadow-color) / 0.22)",
  color: "rgb(var(--ink))",
  fontSize: "12px",
  fontFamily: "var(--font-body)",
  padding: "8px 12px",
};

export const tooltipItemStyle = { color: "rgb(var(--ink))", padding: "1px 0" };
export const tooltipLabelStyle = {
  color: "rgb(var(--ink-muted))",
  fontWeight: 600,
  marginBottom: 2,
};
