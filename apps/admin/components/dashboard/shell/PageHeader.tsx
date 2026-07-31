"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/dashboard/nav";
import { accentClassesForPath } from "@/lib/dashboard/accents";
import { FilterMenu, FilterChips } from "./FilterMenu";

export type Crumb = { label: string; href?: string };

/**
 * Responsive page header — the top of the shared page grammar
 * (breadcrumb → header → KPI band → content).
 *
 * The eyebrow and the module icon chip are tinted with the current module's
 * accent (resolved from the pathname via `lib/dashboard/accents`), giving each
 * domain a subtle identity without any per-page colour. When `showFilters` is
 * set, the consolidated Filters popover + active chips replace the old 6-pill
 * wall (same FiltersProvider contract).
 */
export function ResponsivePageHeader({
  eyebrow,
  title,
  description,
  actions,
  showFilters = false,
  breadcrumb,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  showFilters?: boolean;
  breadcrumb?: Crumb[];
  className?: string;
}) {
  const pathname = usePathname();
  const accent = accentClassesForPath(pathname);
  const navItem = NAV_ITEMS.find((i) => pathname === i.href || pathname.startsWith(`${i.href}/`));
  const Icon = navItem?.icon;

  return (
    <div className={cn("mb-6", className)}>
      {breadcrumb && breadcrumb.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2 flex items-center gap-1.5 text-xs text-ink-muted">
          {breadcrumb.map((c, i) => (
            <span key={`${c.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight className="h-3 w-3 text-ink-faint" />}
              {c.href ? (
                <Link href={c.href} className="transition-colors hover:text-ink">
                  {c.label}
                </Link>
              ) : (
                <span className={cn(i === breadcrumb.length - 1 && "font-medium text-ink")}>{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <span className={cn("mt-0.5 hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl sm:flex", accent.chip)}>
              <Icon className="h-[22px] w-[22px]" />
            </span>
          )}
          <div className="min-w-0">
            {eyebrow && (
              <p className={cn("mb-1 text-xxs font-semibold uppercase tracking-eyebrow", accent.text)}>{eyebrow}</p>
            )}
            <h1 className="font-display text-page-title font-bold tracking-tight text-ink">{title}</h1>
            {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-muted">{description}</p>}
          </div>
        </div>
        {(showFilters || actions) && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {showFilters && <FilterMenu />}
            {actions}
          </div>
        )}
      </div>

      {showFilters && <FilterChips className="mt-3" />}
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
