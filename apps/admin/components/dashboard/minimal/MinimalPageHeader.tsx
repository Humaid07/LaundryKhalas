import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal page header — the calm top of every non-overview main page.
 * Title + one short explanation + (optional) a single primary action.
 *
 * Progressive disclosure rule: the header explains WHAT the page is in one line;
 * it never carries record actions or dense controls. Keep the description to a
 * single muted sentence. See docs/architecture/minimal-dashboard-design-system.md.
 */
export function MinimalPageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  /** A SINGLE primary action, right-aligned. Secondary/record actions belong on detail pages. */
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{eyebrow}</p>
        )}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">{description}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}
