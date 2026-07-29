/**
 * Facility section-accent system — single source of truth for the partner
 * dashboard's colour-coding. Each section has ONE distinct accent used
 * everywhere (sidebar, bottom nav, page eyebrow/icon) so a section's colour is
 * identical in the nav and on its pages. Mirrors apps/admin's `lib/dashboard/accents`.
 *
 * Accents are wayfinding only — never a status colour (status uses the semantic
 * success/warning/danger/info tokens). Rose stays the master BRAND colour and is
 * intentionally NOT assigned to a section. Green/lime hues are avoided.
 *
 * NOTE: every class string is a *literal* so Tailwind's JIT compiler scans it —
 * never build `bg-accent-${name}` dynamically.
 */

export type AccentName =
  | "rose" // brand (not a section)
  | "teal" // Home
  | "sky" // Orders
  | "violet" // Drivers
  | "cyan" // Finance
  | "amber" // Issues
  | "slate"
  | "indigo"
  | "fuchsia"
  | "steel"
  | "plum"
  | "neutral"; // Settings

/** First route segment → accent. "" (home) maps via the "home" key. */
export const MODULE_ACCENT: Record<string, AccentName> = {
  home: "teal",
  orders: "sky",
  drivers: "violet",
  finance: "cyan",
  issues: "amber",
  settings: "neutral",
};

export type AccentClasses = {
  text: string;
  chip: string;
  rail: string;
  softBg: string;
  hoverBg: string;
  strongBg: string;
  ring: string;
  dot: string;
};

export const ACCENT_CLASSES: Record<AccentName, AccentClasses> = {
  rose: { text: "text-rose", chip: "bg-rose/12 text-rose", rail: "bg-rose", softBg: "bg-rose/10", hoverBg: "hover:bg-rose/[0.08]", strongBg: "bg-rose/20", ring: "ring-rose/25", dot: "bg-rose" },
  teal: { text: "text-accent-teal", chip: "bg-accent-teal/12 text-accent-teal", rail: "bg-accent-teal", softBg: "bg-accent-teal/10", hoverBg: "hover:bg-accent-teal/[0.08]", strongBg: "bg-accent-teal/20", ring: "ring-accent-teal/25", dot: "bg-accent-teal" },
  sky: { text: "text-accent-sky", chip: "bg-accent-sky/12 text-accent-sky", rail: "bg-accent-sky", softBg: "bg-accent-sky/10", hoverBg: "hover:bg-accent-sky/[0.08]", strongBg: "bg-accent-sky/20", ring: "ring-accent-sky/25", dot: "bg-accent-sky" },
  violet: { text: "text-accent-violet", chip: "bg-accent-violet/12 text-accent-violet", rail: "bg-accent-violet", softBg: "bg-accent-violet/10", hoverBg: "hover:bg-accent-violet/[0.08]", strongBg: "bg-accent-violet/20", ring: "ring-accent-violet/25", dot: "bg-accent-violet" },
  cyan: { text: "text-accent-cyan", chip: "bg-accent-cyan/12 text-accent-cyan", rail: "bg-accent-cyan", softBg: "bg-accent-cyan/10", hoverBg: "hover:bg-accent-cyan/[0.08]", strongBg: "bg-accent-cyan/20", ring: "ring-accent-cyan/25", dot: "bg-accent-cyan" },
  amber: { text: "text-accent-amber", chip: "bg-accent-amber/14 text-accent-amber", rail: "bg-accent-amber", softBg: "bg-accent-amber/12", hoverBg: "hover:bg-accent-amber/[0.10]", strongBg: "bg-accent-amber/20", ring: "ring-accent-amber/25", dot: "bg-accent-amber" },
  slate: { text: "text-accent-slate", chip: "bg-accent-slate/14 text-accent-slate", rail: "bg-accent-slate", softBg: "bg-accent-slate/12", hoverBg: "hover:bg-accent-slate/[0.10]", strongBg: "bg-accent-slate/20", ring: "ring-accent-slate/25", dot: "bg-accent-slate" },
  indigo: { text: "text-accent-indigo", chip: "bg-accent-indigo/12 text-accent-indigo", rail: "bg-accent-indigo", softBg: "bg-accent-indigo/10", hoverBg: "hover:bg-accent-indigo/[0.08]", strongBg: "bg-accent-indigo/20", ring: "ring-accent-indigo/25", dot: "bg-accent-indigo" },
  fuchsia: { text: "text-accent-fuchsia", chip: "bg-accent-fuchsia/12 text-accent-fuchsia", rail: "bg-accent-fuchsia", softBg: "bg-accent-fuchsia/10", hoverBg: "hover:bg-accent-fuchsia/[0.08]", strongBg: "bg-accent-fuchsia/20", ring: "ring-accent-fuchsia/25", dot: "bg-accent-fuchsia" },
  steel: { text: "text-accent-steel", chip: "bg-accent-steel/14 text-accent-steel", rail: "bg-accent-steel", softBg: "bg-accent-steel/12", hoverBg: "hover:bg-accent-steel/[0.10]", strongBg: "bg-accent-steel/20", ring: "ring-accent-steel/25", dot: "bg-accent-steel" },
  plum: { text: "text-accent-plum", chip: "bg-accent-plum/12 text-accent-plum", rail: "bg-accent-plum", softBg: "bg-accent-plum/10", hoverBg: "hover:bg-accent-plum/[0.08]", strongBg: "bg-accent-plum/20", ring: "ring-accent-plum/25", dot: "bg-accent-plum" },
  neutral: { text: "text-ink-muted", chip: "bg-ink/8 text-ink-muted", rail: "bg-ink-faint", softBg: "bg-ink/6", hoverBg: "hover:bg-ink/[0.05]", strongBg: "bg-ink/12", ring: "ring-border", dot: "bg-ink-faint" },
};

/** Resolve the accent for a pathname (empty first segment = Home). */
export function accentForPath(pathname: string | null | undefined): AccentName {
  const seg = (pathname ?? "").split("/").filter(Boolean)[0] ?? "home";
  return MODULE_ACCENT[seg || "home"] ?? "rose";
}

/** Resolve the accent for an href like "/orders" or "/". */
export function accentForHref(href: string): AccentName {
  return accentForPath(href);
}

export function accentClasses(name: AccentName): AccentClasses {
  return ACCENT_CLASSES[name];
}

export function accentClassesForPath(pathname: string | null | undefined): AccentClasses {
  return ACCENT_CLASSES[accentForPath(pathname)];
}
