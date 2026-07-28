/** Formatting helpers for the facility dashboard. Currency defaults to AED (home market). */

export function formatCurrency(value: number, currency = "AED", compact = false): string {
  return new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}

/**
 * Money formatter for exact customer-facing amounts. Whole numbers render clean
 * ("AED 63"); anything with a fractional part shows two decimals ("AED 7.35").
 */
export function formatMoney(value: number, currency = "AED"): string {
  const rounded = Math.round(value * 100) / 100;
  const isWhole = Number.isInteger(rounded);
  return new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency,
    minimumFractionDigits: isWhole ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(rounded);
}

export function formatNumber(value: number, compact = false): string {
  return new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}

/** Relative "time ago" for timestamps. Returns "just now", "3h ago", "2d ago". */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Absolute date/time, short form: "12 Jul, 14:30". */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Date only: "12 Jul 2026". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * Safely format a line-item's pricing unit / measure for display.
 *
 * Line items come from Supabase order snapshots, so this value is genuinely
 * `unknown` at runtime: it may be a string unit ("kg"), a numeric measure
 * (30 sqm), null/undefined, or a malformed object in older snapshots. Calling
 * `.toLowerCase()` on a non-string crashed the order detail page — so everything
 * routes through here. Returns "" for anything we can't render, so callers can
 * hide the separator instead of showing junk.
 */
export function formatPricingUnit(value: unknown): string {
  if (typeof value === "string") return value.trim().toLowerCase();
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  if (typeof value === "object") return "";
  return String(value).toLowerCase();
}

/** Safe quantity for display: numeric → its value, else 1. Never renders an object. */
export function formatQuantity(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "") return value.trim();
  return "1";
}
