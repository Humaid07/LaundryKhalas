import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * SectionCard — a soft, titled block for grouping content on main pages
 * (Overview panels, settings sections). Lighter than DetailSectionCard.
 */
export function SectionCard({
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
