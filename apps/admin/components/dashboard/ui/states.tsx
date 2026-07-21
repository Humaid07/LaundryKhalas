import type { ComponentType, ReactNode } from "react";
import { Inbox, Loader2, SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface-2 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-rose/10 text-rose">
        <Icon className="h-5 w-5" />
      </span>
      <p className="font-display text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-xs text-xs text-ink-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center justify-center gap-2 py-12 text-sm text-ink-muted", className)}>
      <Loader2 className="h-4 w-4 animate-spin text-rose" />
      {label}
    </div>
  );
}

/** Skeleton shimmer block for loading placeholders. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-ink/8", className)} />;
}

/**
 * Empty state shown when the active global filters exclude every row. Names the
 * active filter context and offers a one-click reset, so a filtered-away list is
 * never mistaken for "no data" and never leaves stale rows on screen.
 */
export function FilteredEmptyState({
  context,
  onClear,
  entity = "records",
  className,
}: {
  /** Human-readable active filter context, e.g. "Dubai · UAE · Dry Cleaning". */
  context?: string;
  onClear?: () => void;
  entity?: string;
  className?: string;
}) {
  return (
    <EmptyState
      icon={SlidersHorizontal}
      title={`No ${entity} match the selected filters`}
      description={context ? `Active filters: ${context}` : undefined}
      className={className}
      action={
        onClear ? (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-9 items-center gap-1 rounded-full border border-border px-3.5 text-xxs font-semibold text-ink-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
          >
            <X className="h-3 w-3" /> Clear filters
          </button>
        ) : undefined
      }
    />
  );
}

/**
 * Small inline badge for KPI grids / aggregate charts that are period snapshots
 * and are NOT re-computed per filter. Shown only while filters are active so the
 * UI never implies a headline number responds to the geo/date scope when it does
 * not. See docs/architecture/dashboard-filter-system.md ("snapshot vs filtered").
 */
export function SnapshotBadge({ active, label = "Overall snapshot", className }: { active: boolean; label?: string; className?: string }) {
  if (!active) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xxs font-medium text-ink-muted",
        className,
      )}
      title="This is a period snapshot and is not narrowed by the active filters."
    >
      <SlidersHorizontal className="h-3 w-3 text-ink-faint" /> {label}
    </span>
  );
}
