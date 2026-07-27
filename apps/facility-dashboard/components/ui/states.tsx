import type { ComponentType, ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
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
 * Error state with an optional retry. Used when an API call fails so the operator
 * always sees a clear, recoverable message instead of a blank screen.
 */
export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-danger/30 bg-danger/5 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <p className="font-display text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-xs text-xs text-ink-muted">{description}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-full border border-border bg-surface px-4 text-xs font-semibold text-ink transition-colors hover:border-border-strong hover:bg-surface-2"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}
