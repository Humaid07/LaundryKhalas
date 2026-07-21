import type { ReactNode } from "react";
import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { SECTIONS } from "@/lib/dashboard/sections";
import { SectionSubNav } from "./SectionSubNav";

/**
 * Wrapper for a subsection route page: breadcrumb + pill sub-nav, then a focused
 * page header (title/description from the section config), then the focused
 * content. Keeps every subsection route file tiny and consistent.
 */
export function SubsectionShell({
  sectionKey,
  slug,
  actions,
  showFilters,
  children,
}: {
  sectionKey: string;
  slug: string;
  actions?: ReactNode;
  /** Override the global filter bar. Defaults to the section's `filterable` flag. */
  showFilters?: boolean;
  children: ReactNode;
}) {
  const section = SECTIONS[sectionKey];
  const sub = section?.subsections.find((s) => s.slug === slug);
  // Global filter bar shows on every subsection of a filterable section unless
  // the page explicitly overrides. Keeps filter coverage consistent everywhere.
  const withFilters = showFilters ?? section?.filterable !== false;
  return (
    <div className="lk-enter">
      <SectionSubNav sectionKey={sectionKey} />
      <ResponsivePageHeader
        title={sub?.label ?? section?.title ?? ""}
        description={sub?.description}
        actions={actions}
        showFilters={withFilters}
      />
      {children}
    </div>
  );
}
