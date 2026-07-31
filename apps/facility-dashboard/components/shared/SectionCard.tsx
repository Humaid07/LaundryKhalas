"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { accentClassesForPath, accentClasses, type AccentName } from "@/lib/accents";

/**
 * SectionCard — a soft, titled block for grouping content on main pages
 * (Overview panels, settings sections). Its header icon uses the section accent
 * (resolved from the route, or an explicit `accent`). Lighter than DetailSectionCard.
 */
export function SectionCard({
  title,
  icon: Icon,
  action,
  accent,
  children,
  className,
  bodyClassName,
}: {
  title?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  accent?: AccentName;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  const pathname = usePathname();
  const a = accent ? accentClasses(accent) : accentClassesForPath(pathname);
  return (
    <section className={cn("rounded-2xl border border-border bg-surface shadow-card", className)}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            {Icon && <Icon className={cn("h-4 w-4", a.text)} />}
            <h2 className="font-display text-card-title font-semibold text-ink">{title}</h2>
          </div>
          {action}
        </header>
      )}
      <div className={cn("px-5 py-4", bodyClassName)}>{children}</div>
    </section>
  );
}
