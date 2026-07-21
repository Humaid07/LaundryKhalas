import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/dashboard/types";
import { toneChip, toneDot } from "./tones";

/* -------------------------------- Panel/Card -------------------------------- */

export function Panel({
  className,
  children,
  padded = true,
}: {
  className?: string;
  children: ReactNode;
  padded?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-border bg-surface shadow-card",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        <h3 className="font-display text-[0.95rem] font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
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
