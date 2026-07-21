"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { SECTIONS } from "@/lib/dashboard/sections";
import { cn } from "@/lib/utils";

/**
 * Breadcrumb (`Section / <Subsection>`) + a scrollable pill row of the section's
 * subsections. Keeps each subsection on its own focused page while giving quick
 * in-section navigation. Active state derived from the pathname. Config-driven
 * from `lib/dashboard/sections.ts` so it works for every section.
 */
export function SectionSubNav({ sectionKey }: { sectionKey: string }) {
  const pathname = usePathname();
  const section = SECTIONS[sectionKey];
  if (!section) return null;
  const active = section.subsections.find((s) => pathname.startsWith(`${section.base}/${s.slug}`));

  return (
    <div className="mb-6 space-y-3">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-ink-muted">
        <Link href={section.base} className="transition-colors hover:text-ink">{section.title}</Link>
        {active && (
          <>
            <ChevronRight className="h-3 w-3 text-ink-faint" />
            <span className="font-medium text-ink">{active.label}</span>
          </>
        )}
      </nav>
      <div className="overflow-x-auto">
        <div role="tablist" className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
          {section.subsections.map((s) => {
            const on = active?.slug === s.slug;
            const Icon = s.icon;
            return (
              <Link
                key={s.slug}
                href={`${section.base}/${s.slug}`}
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
