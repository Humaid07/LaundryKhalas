import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * MobilePageHeader — the calm title block at the top of a page. Title +
 * optional one-line description + optional single action. Mobile-first spacing.
 */
export function MobilePageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{eyebrow}</p>
        )}
        <h1 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-muted">{description}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}
