"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Headset, Factory, Truck, ClipboardList, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** The four Operations subsections — single source of truth for nav + landing. */
export const OPERATIONS_SUBSECTIONS = [
  { slug: "customer-facing", label: "Customer Facing", icon: Headset },
  { slug: "facility-facing", label: "Facility Facing", icon: Factory },
  { slug: "drivers", label: "Drivers", icon: Truck },
  { slug: "customer-orders", label: "Customer Orders", icon: ClipboardList },
] as const;

/**
 * Breadcrumb (Operations / <Section>) + a scrollable pill row linking the four
 * Operations subsections. Keeps each subsection on its own clean page instead of
 * one crowded tab strip. Active state is derived from the pathname.
 */
export function OperationsSubNav() {
  const pathname = usePathname();
  const active = OPERATIONS_SUBSECTIONS.find((s) => pathname.startsWith(`/operations/${s.slug}`));

  return (
    <div className="mb-6 space-y-3">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-ink-muted">
        <Link href="/operations" className="transition-colors hover:text-ink">Operations</Link>
        {active && (
          <>
            <ChevronRight className="h-3 w-3 text-ink-faint" />
            <span className="font-medium text-ink">{active.label}</span>
          </>
        )}
      </nav>
      <div className="overflow-x-auto">
        <div role="tablist" className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
          {OPERATIONS_SUBSECTIONS.map((s) => {
            const on = active?.slug === s.slug;
            const Icon = s.icon;
            return (
              <Link
                key={s.slug}
                href={`/operations/${s.slug}`}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold transition-all duration-200",
                  on ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
                )}
              >
                <Icon className="h-4 w-4" />
                {s.label}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
