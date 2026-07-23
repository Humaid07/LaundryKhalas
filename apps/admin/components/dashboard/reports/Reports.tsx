"use client";

import { FileText } from "lucide-react";
import type { Tone } from "@/lib/dashboard/types";
import { reportDetails } from "@/lib/dashboard/reports-data";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { activeFilterCount } from "@/lib/dashboard/filters";
import {
  MinimalKpiStrip, RecordList, CompactRecordCard, EmptyState, SnapshotBadge,
  type MinimalKpi,
} from "@/components/dashboard/minimal";

/**
 * Renders one Report subsection by slug (see lib/dashboard/sections.ts).
 *
 * Progressive disclosure: the main page stays light — a one-line purpose, a small
 * KPI strip of the top figures, and a short list of the report's sections as
 * preview cards. The full report (figures, tables, breakdown) and all actions
 * (export / share) live on the detail page at /reports/view/<slug>.
 */
export function ReportSubsection({ slug }: { slug: string }) {
  const { filters } = useFilters();
  const r = reportDetails[slug];
  if (!r) {
    return (
      <div className="space-y-6">
        <EmptyState icon={FileText} title="Report not found" description="This report has no detail yet." />
      </div>
    );
  }

  const isFiltered = activeFilterCount(filters) > 0;
  const detailHref = `/reports/view/${slug}`;

  const kpis: MinimalKpi[] = r.metrics.slice(0, 4).map((m) => ({ label: m.label, value: m.value }));

  const sections: { key: string; label: string; tone: Tone; items: string[] }[] = [
    { key: "changed", label: "What changed", tone: "success", items: r.changed },
    { key: "risks", label: "Risks & blockers", tone: "warning", items: r.risks },
    { key: "next", label: "Next actions", tone: "info", items: r.next },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-sm leading-relaxed text-ink-muted">{r.summary}</p>
        <SnapshotBadge active={isFiltered} />
      </div>

      <MinimalKpiStrip kpis={kpis} />

      <RecordList>
        {sections.map((s) => (
          <CompactRecordCard
            key={s.key}
            title={s.label}
            status={{ label: `${s.items.length} ${s.items.length === 1 ? "item" : "items"}`, tone: s.tone }}
            fields={s.items.slice(0, 2).map((it, i) => ({ label: i === 0 ? "Highlight" : "Also", value: it }))}
            meta={<span className="text-xxs text-ink-faint">Full report</span>}
            href={`${detailHref}#${s.key}`}
          />
        ))}
      </RecordList>
    </div>
  );
}
