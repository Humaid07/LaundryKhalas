import type { Tone } from "@/lib/dashboard/types";

/** Tone → soft badge/chip classes. Rose is the brand signal; plum & neutral
 *  fall back to chart CSS vars so every tone reads correctly in dark mode. */
export const toneChip: Record<Tone, string> = {
  rose: "bg-rose/12 text-rose ring-1 ring-inset ring-rose/20",
  success: "bg-success/12 text-success ring-1 ring-inset ring-success/20",
  warning: "bg-warning/14 text-warning ring-1 ring-inset ring-warning/25",
  danger: "bg-danger/12 text-danger ring-1 ring-inset ring-danger/20",
  info: "bg-info/12 text-info ring-1 ring-inset ring-info/20",
  neutral: "bg-ink/8 text-ink-muted ring-1 ring-inset ring-border",
  plum: "bg-[rgb(var(--c-plum)/0.14)] text-[rgb(var(--c-plum))] ring-1 ring-inset ring-[rgb(var(--c-plum)/0.22)]",
};

export const toneDot: Record<Tone, string> = {
  rose: "bg-rose",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  neutral: "bg-ink-faint",
  plum: "bg-[rgb(var(--c-plum))]",
};

export const toneText: Record<Tone, string> = {
  rose: "text-rose",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
  neutral: "text-ink-muted",
  plum: "text-[rgb(var(--c-plum))]",
};
