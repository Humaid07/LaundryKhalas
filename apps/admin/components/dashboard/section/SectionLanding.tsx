import type { ReactNode } from "react";
import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { SECTIONS } from "@/lib/dashboard/sections";
import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";

const colClass: Record<number, string> = {
  2: "md:grid-cols-2",
  3: "md:grid-cols-2 xl:grid-cols-3",
  4: "md:grid-cols-2 xl:grid-cols-4",
};

/**
 * Reusable landing page for a top-level section: header + a clean grid of
 * subsection cards (summary + navigation only — no heavy tables/charts).
 */
export function SectionLanding({ sectionKey, actions }: { sectionKey: string; actions?: ReactNode }) {
  const section = SECTIONS[sectionKey];
  if (!section) return null;
  return (
    <div className="lk-enter">
      <ResponsivePageHeader
        eyebrow={section.eyebrow}
        title={section.title}
        description={section.description}
        actions={actions}
        showFilters={section.filterable !== false}
      />
      <div className={cn("grid gap-4", colClass[section.cols ?? 3])}>
        {section.subsections.map((sub) => (
          <SectionCard key={sub.slug} base={section.base} sub={sub} />
        ))}
      </div>
    </div>
  );
}
