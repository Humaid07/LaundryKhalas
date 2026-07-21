/** Formatting helpers for the dashboard. Currency defaults to AED (home market). */

export function formatCurrency(value: number, currency = "AED", compact = false): string {
  return new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}

export function formatNumber(value: number, compact = false): string {
  return new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return `${value > 0 ? "" : ""}${value.toFixed(digits)}%`;
}

export function formatDelta(value: number, digits = 1): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

/**
 * Fixed "now" for the mock dataset. Relative times are computed against this
 * instead of the real `Date.now()` so the value is DETERMINISTIC: statically
 * prerendered HTML and client hydration produce identical strings (no React
 * hydration text mismatch / #425), and the demo reads consistently against the
 * mock timeline (events clustered around 2026-07-20). Aligns with `TODAY` in
 * `lib/dashboard/filters.ts`.
 */
export const MOCK_NOW = "2026-07-20T10:00:00Z";

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = new Date(MOCK_NOW).getTime();
  const diff = Math.round((now - then) / 1000);
  const abs = Math.abs(diff);
  const future = diff < 0;
  const units: [number, string][] = [
    [60, "sec"],
    [3600, "min"],
    [86400, "hr"],
    [604800, "day"],
  ];
  if (abs < 60) return future ? "in a moment" : "just now";
  for (let i = units.length - 1; i >= 0; i--) {
    const [secs, label] = units[i];
    if (abs >= secs) {
      const n = Math.round(abs / secs);
      return future ? `in ${n} ${label}${n > 1 ? "s" : ""}` : `${n} ${label}${n > 1 ? "s" : ""} ago`;
    }
  }
  return future ? "soon" : "just now";
}

/**
 * Chat-bubble clock, e.g. "9:52 AM". Formatted from the ISO's UTC components so
 * it is DETERMINISTIC across server render and client hydration (no timezone
 * drift, no React #425 mismatch) — same rationale as {@link MOCK_NOW}.
 */
export function formatClock(iso: string): string {
  const d = new Date(iso);
  let h = d.getUTCHours();
  const m = d.getUTCMinutes().toString().padStart(2, "0");
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${m} ${ampm}`;
}

export function maskPhone(phone: string): string {
  // Keep country code + last 2 digits, mask the middle. +971 50 •••• 12
  const digits = phone.replace(/[^\d+]/g, "");
  if (digits.length < 6) return "•••• ••••";
  const head = digits.slice(0, 5);
  const tail = digits.slice(-2);
  return `${head} •••• ${tail}`;
}
