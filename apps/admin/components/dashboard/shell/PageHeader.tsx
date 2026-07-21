import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { FilterBar } from "./FilterBar";

/** Responsive page header: eyebrow, title, description, action slot, and an
 *  optional global filter bar underneath. */
export function ResponsivePageHeader({
  eyebrow,
  title,
  description,
  actions,
  showFilters = false,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  showFilters?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("mb-6", className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow && (
            <p className="mb-1 text-xxs font-semibold uppercase tracking-eyebrow text-rose">{eyebrow}</p>
          )}
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink md:text-[1.7rem]">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {showFilters && (
        <div className="mt-4 rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
          <FilterBar />
        </div>
      )}
    </div>
  );
}

/** Section heading used inside pages, between panels. */
export function SectionTitle({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-4", className)}>
      <div>
        <h2 className="font-display text-base font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-xs text-ink-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
