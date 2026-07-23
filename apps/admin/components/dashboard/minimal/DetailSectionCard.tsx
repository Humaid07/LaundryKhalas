import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/dashboard/types";
import { StatusBadge } from "@/components/dashboard/ui/primitives";

/**
 * DetailSectionCard — a spacious, softly-bordered block used to group one topic
 * on a detail page (customer, payment, lifecycle, …). Detail pages compose a
 * stack of these. Generous padding, quiet header, subtle border.
 */
export function DetailSectionCard({
  title,
  icon: Icon,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("rounded-2xl border border-border/70 bg-surface shadow-card", className)}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            {Icon && <Icon className="h-4 w-4 text-rose" />}
            <h2 className="font-display text-[0.95rem] font-semibold text-ink">{title}</h2>
          </div>
          {action}
        </header>
      )}
      <div className={cn("px-5 py-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/** A label/value pair. `mono` for IDs. */
export function Field({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className={cn("mt-1 break-words text-sm font-medium text-ink", mono && "font-mono")}>{value ?? "—"}</dd>
    </div>
  );
}

export function FieldGrid({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return <dl className={cn("grid gap-x-6 gap-y-4", cols === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2")}>{children}</dl>;
}

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <StatusBadge tone={tone} dot={false}>
      {children}
    </StatusBadge>
  );
}
