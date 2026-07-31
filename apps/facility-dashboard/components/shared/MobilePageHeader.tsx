"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { accentClassesForPath } from "@/lib/accents";

/**
 * MobilePageHeader — the calm title block at the top of a page. Title +
 * optional one-line description + optional single action. The eyebrow and an
 * optional icon chip pick up the section's accent (resolved from the route), so
 * each section reads with its own identity. Mobile-first spacing.
 */
export function MobilePageHeader({
  eyebrow,
  title,
  description,
  action,
  icon: Icon,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: LucideIcon;
  className?: string;
}) {
  const accent = accentClassesForPath(usePathname());
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {Icon && (
          <span className={cn("mt-0.5 hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl sm:flex", accent.chip)}>
            <Icon className="h-5 w-5" />
          </span>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <p className={cn("mb-1 text-xxs font-semibold uppercase tracking-eyebrow", accent.text)}>{eyebrow}</p>
          )}
          <h1 className="font-display text-page-title font-semibold tracking-tight text-ink">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-muted">{description}</p>}
        </div>
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}
