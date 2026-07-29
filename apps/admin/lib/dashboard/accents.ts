/**
 * Module-accent system — the single source of truth for the dashboard's ERP
 * colour-coding. Each top-level section has ONE distinct accent, used everywhere
 * (sidebar, page eyebrow, icon chip, section rule, landing-card rule, ⌘K palette)
 * so a section's colour is identical in the nav and on its pages.
 *
 * Accents are wayfinding only — never a status colour (status uses the semantic
 * success/warning/danger/info tokens). Rose stays the master BRAND colour
 * (logo, primary actions, active brand dot) and is intentionally NOT assigned to
 * any section, so brand rose never competes with section identity. Green/lime
 * hues are avoided (they read as `success`).
 *
 * NOTE: every class string below is a *literal* so Tailwind's JIT compiler sees
 * it. Do not build these dynamically (e.g. `bg-accent-${name}`) — unscanned
 * classes get purged.
 */

export type AccentName =
  | "rose" // brand (not a section)
  | "slate" // Overview
  | "teal" // Operations
  | "sky" // Orders
  | "amber" // Sales
  | "violet" // Partner Acquisition
  | "indigo" // SEO Agents
  | "fuchsia" // Marketing
  | "cyan" // Finance & Compliance
  | "steel" // Dev & Automation
  | "plum" // Reports
  | "orange" // Facilities
  | "neutral"; // Settings

/** Top-level route segment → its unique accent. One line per section. */
export const MODULE_ACCENT: Record<string, AccentName> = {
  overview: "slate",
  operations: "teal",
  orders: "sky",
  sales: "amber",
  "partner-acquisition": "violet",
  "seo-agents": "indigo",
  marketing: "fuchsia",
  "finance-compliance": "cyan",
  "dev-automation": "steel",
  reports: "plum",
  facilities: "orange",
  settings: "neutral",
};

export type AccentClasses = {
  /** Accent text colour. */
  text: string;
  /** Icon-chip: soft accent-tinted background + accent text. */
  chip: string;
  /** Solid accent fill (top-rule / rail / active dot). */
  rail: string;
  /** Soft accent-tinted background (active nav row). */
  softBg: string;
  /** Section-tinted hover background (hover: variant, softer than active). */
  hoverBg: string;
  /** Slightly stronger accent-tinted background (badges, active emphasis). */
  strongBg: string;
  /** Accent ring (inset). */
  ring: string;
  /** Accent hover-border for cards. */
  hoverBorder: string;
  /** Solid accent dot. */
  dot: string;
  /** Group-hover fill for a CTA pill (solid accent bg + readable text). */
  ctaHover: string;
};

/** Literal class maps per accent (see NOTE above about JIT scanning). */
export const ACCENT_CLASSES: Record<AccentName, AccentClasses> = {
  rose: {
    text: "text-rose",
    chip: "bg-rose/12 text-rose",
    rail: "bg-rose",
    softBg: "bg-rose/10",
    hoverBg: "hover:bg-rose/[0.08]",
    strongBg: "bg-rose/20",
    ring: "ring-rose/25",
    hoverBorder: "hover:border-rose/40",
    dot: "bg-rose",
    ctaHover: "group-hover:bg-rose group-hover:text-rose-contrast",
  },
  slate: {
    text: "text-accent-slate",
    chip: "bg-accent-slate/14 text-accent-slate",
    rail: "bg-accent-slate",
    softBg: "bg-accent-slate/12",
    hoverBg: "hover:bg-accent-slate/[0.10]",
    strongBg: "bg-accent-slate/20",
    ring: "ring-accent-slate/25",
    hoverBorder: "hover:border-accent-slate/40",
    dot: "bg-accent-slate",
    ctaHover: "group-hover:bg-accent-slate group-hover:text-white",
  },
  teal: {
    text: "text-accent-teal",
    chip: "bg-accent-teal/12 text-accent-teal",
    rail: "bg-accent-teal",
    softBg: "bg-accent-teal/10",
    hoverBg: "hover:bg-accent-teal/[0.08]",
    strongBg: "bg-accent-teal/20",
    ring: "ring-accent-teal/25",
    hoverBorder: "hover:border-accent-teal/40",
    dot: "bg-accent-teal",
    ctaHover: "group-hover:bg-accent-teal group-hover:text-white",
  },
  sky: {
    text: "text-accent-sky",
    chip: "bg-accent-sky/12 text-accent-sky",
    rail: "bg-accent-sky",
    softBg: "bg-accent-sky/10",
    hoverBg: "hover:bg-accent-sky/[0.08]",
    strongBg: "bg-accent-sky/20",
    ring: "ring-accent-sky/25",
    hoverBorder: "hover:border-accent-sky/40",
    dot: "bg-accent-sky",
    ctaHover: "group-hover:bg-accent-sky group-hover:text-white",
  },
  amber: {
    text: "text-accent-amber",
    chip: "bg-accent-amber/14 text-accent-amber",
    rail: "bg-accent-amber",
    softBg: "bg-accent-amber/12",
    hoverBg: "hover:bg-accent-amber/[0.10]",
    strongBg: "bg-accent-amber/20",
    ring: "ring-accent-amber/25",
    hoverBorder: "hover:border-accent-amber/40",
    dot: "bg-accent-amber",
    ctaHover: "group-hover:bg-accent-amber group-hover:text-white",
  },
  violet: {
    text: "text-accent-violet",
    chip: "bg-accent-violet/12 text-accent-violet",
    rail: "bg-accent-violet",
    softBg: "bg-accent-violet/10",
    hoverBg: "hover:bg-accent-violet/[0.08]",
    strongBg: "bg-accent-violet/20",
    ring: "ring-accent-violet/25",
    hoverBorder: "hover:border-accent-violet/40",
    dot: "bg-accent-violet",
    ctaHover: "group-hover:bg-accent-violet group-hover:text-white",
  },
  indigo: {
    text: "text-accent-indigo",
    chip: "bg-accent-indigo/12 text-accent-indigo",
    rail: "bg-accent-indigo",
    softBg: "bg-accent-indigo/10",
    hoverBg: "hover:bg-accent-indigo/[0.08]",
    strongBg: "bg-accent-indigo/20",
    ring: "ring-accent-indigo/25",
    hoverBorder: "hover:border-accent-indigo/40",
    dot: "bg-accent-indigo",
    ctaHover: "group-hover:bg-accent-indigo group-hover:text-white",
  },
  fuchsia: {
    text: "text-accent-fuchsia",
    chip: "bg-accent-fuchsia/12 text-accent-fuchsia",
    rail: "bg-accent-fuchsia",
    softBg: "bg-accent-fuchsia/10",
    hoverBg: "hover:bg-accent-fuchsia/[0.08]",
    strongBg: "bg-accent-fuchsia/20",
    ring: "ring-accent-fuchsia/25",
    hoverBorder: "hover:border-accent-fuchsia/40",
    dot: "bg-accent-fuchsia",
    ctaHover: "group-hover:bg-accent-fuchsia group-hover:text-white",
  },
  cyan: {
    text: "text-accent-cyan",
    chip: "bg-accent-cyan/12 text-accent-cyan",
    rail: "bg-accent-cyan",
    softBg: "bg-accent-cyan/10",
    hoverBg: "hover:bg-accent-cyan/[0.08]",
    strongBg: "bg-accent-cyan/20",
    ring: "ring-accent-cyan/25",
    hoverBorder: "hover:border-accent-cyan/40",
    dot: "bg-accent-cyan",
    ctaHover: "group-hover:bg-accent-cyan group-hover:text-white",
  },
  steel: {
    text: "text-accent-steel",
    chip: "bg-accent-steel/14 text-accent-steel",
    rail: "bg-accent-steel",
    softBg: "bg-accent-steel/12",
    hoverBg: "hover:bg-accent-steel/[0.10]",
    strongBg: "bg-accent-steel/20",
    ring: "ring-accent-steel/25",
    hoverBorder: "hover:border-accent-steel/40",
    dot: "bg-accent-steel",
    ctaHover: "group-hover:bg-accent-steel group-hover:text-white",
  },
  plum: {
    text: "text-accent-plum",
    chip: "bg-accent-plum/12 text-accent-plum",
    rail: "bg-accent-plum",
    softBg: "bg-accent-plum/10",
    hoverBg: "hover:bg-accent-plum/[0.08]",
    strongBg: "bg-accent-plum/20",
    ring: "ring-accent-plum/25",
    hoverBorder: "hover:border-accent-plum/40",
    dot: "bg-accent-plum",
    ctaHover: "group-hover:bg-accent-plum group-hover:text-white",
  },
  orange: {
    text: "text-accent-orange",
    chip: "bg-accent-orange/12 text-accent-orange",
    rail: "bg-accent-orange",
    softBg: "bg-accent-orange/10",
    hoverBg: "hover:bg-accent-orange/[0.08]",
    strongBg: "bg-accent-orange/20",
    ring: "ring-accent-orange/25",
    hoverBorder: "hover:border-accent-orange/40",
    dot: "bg-accent-orange",
    ctaHover: "group-hover:bg-accent-orange group-hover:text-white",
  },
  neutral: {
    text: "text-ink-muted",
    chip: "bg-ink/8 text-ink-muted",
    rail: "bg-ink-faint",
    softBg: "bg-ink/6",
    hoverBg: "hover:bg-ink/[0.05]",
    strongBg: "bg-ink/12",
    ring: "ring-border",
    hoverBorder: "hover:border-border-strong",
    dot: "bg-ink-faint",
    ctaHover: "group-hover:bg-ink group-hover:text-canvas",
  },
};

/** Resolve the accent name for a pathname (uses the first route segment). */
export function accentForPath(pathname: string | null | undefined): AccentName {
  const seg = (pathname ?? "").split("/").filter(Boolean)[0] ?? "overview";
  return MODULE_ACCENT[seg] ?? "rose";
}

/** Resolve the accent name for an href/base like "/sales". */
export function accentForHref(href: string): AccentName {
  return accentForPath(href);
}

/** Class bundle for an accent name. */
export function accentClasses(name: AccentName): AccentClasses {
  return ACCENT_CLASSES[name];
}

/** Convenience: class bundle straight from a pathname. */
export function accentClassesForPath(pathname: string | null | undefined): AccentClasses {
  return ACCENT_CLASSES[accentForPath(pathname)];
}
