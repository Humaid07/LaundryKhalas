import type { ComponentType, ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/dashboard/types";
import { accentClasses, type AccentName } from "@/lib/dashboard/accents";
import { toneChip, toneDot } from "./tones";

/* -------------------------------- Panel/Card -------------------------------- */

export function Panel({
  className,
  children,
  padded = true,
  accent,
}: {
  className?: string;
  children: ReactNode;
  padded?: boolean;
  /** When set, draws a thin module-accent top-rule. */
  accent?: AccentName;
}) {
  const a = accent ? accentClasses(accent) : null;
  return (
    <section
      className={cn(
        "rounded-2xl border border-border bg-surface shadow-card",
        a && "relative overflow-hidden",
        padded && "p-5",
        className,
      )}
    >
      {a && <span className={cn("pointer-events-none absolute inset-x-0 top-0 h-0.5 opacity-80", a.rail)} />}
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  subtitle,
  action,
  icon: Icon,
  accent,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  /** Optional leading icon rendered in an accent-tinted chip. */
  icon?: ComponentType<{ className?: string }>;
  accent?: AccentName;
  className?: string;
}) {
  const a = accent ? accentClasses(accent) : null;
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-4", className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {Icon && (
          <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", a ? a.chip : "bg-ink/8 text-ink-muted")}>
            <Icon className="h-4 w-4" />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="font-display text-[0.95rem] font-semibold text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* --------------------------------- KpiBand ---------------------------------- */

/**
 * KPI band — the shared page-grammar slot for a page's headline metrics. Wraps a
 * StatGrid (or any KPI row) in a subtly sunken well so the metric cards read as
 * lifted above it (elevation level 0 → level 1). Optional label + right-aligned
 * aside (e.g. a SnapshotBadge). Part of: breadcrumb → header → KPI band → content.
 */
export function KpiBand({
  children,
  label,
  aside,
  className,
}: {
  children: ReactNode;
  label?: ReactNode;
  aside?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mb-6 rounded-2xl border border-border/60 bg-surface-sunken p-3", className)}>
      {(label || aside) && (
        <div className="mb-2 flex items-center justify-between gap-3 px-1">
          {label ? <Eyebrow>{label}</Eyebrow> : <span />}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

/* ------------------------------- Status badge ------------------------------- */

export function StatusBadge({
  children,
  tone = "neutral",
  dot = true,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xxs font-semibold",
        toneChip[tone],
        className,
      )}
    >
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone])} />}
      {children}
    </span>
  );
}

/* --------------------------------- Eyebrow ---------------------------------- */

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        "text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint",
        className,
      )}
    >
      {children}
    </p>
  );
}

/* -------------------------------- Delta chip -------------------------------- */

export function DeltaChip({ delta, className }: { delta: number; className?: string }) {
  const positive = delta > 0;
  const flat = delta === 0;
  const tone: Tone = flat ? "neutral" : positive ? "success" : "danger";
  const arrow = flat ? "→" : positive ? "↑" : "↓";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xxs font-semibold tnum",
        toneChip[tone],
        className,
      )}
    >
      <span aria-hidden>{arrow}</span>
      {Math.abs(delta).toFixed(1)}%
    </span>
  );
}
