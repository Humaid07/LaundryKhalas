"use client";

import { AlertTriangle, TrendingUp, ArrowRight, Download, Share2, Globe2 } from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { EmptyState } from "@/components/dashboard/ui/states";
import { reportDetails } from "@/lib/dashboard/reports-data";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterContextLabel, activeFilterCount } from "@/lib/dashboard/filters";

/** Renders one Report subsection by slug (see lib/dashboard/sections.ts). */
export function ReportSubsection({ slug }: { slug: string }) {
  const { filters } = useFilters();
  const r = reportDetails[slug];
  if (!r) return <EmptyState title="Report not found" description="This report has no detail yet." />;

  // Reports honour the active global filters as a reporting *scope* — the report
  // reads e.g. "Operations Report — Dubai · UAE · Today". Underlying figures are
  // period aggregates (documented), so the scope is shown as context, not faked.
  const scope = filterContextLabel(filters);
  const scoped = activeFilterCount(filters) > 0;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <Panel className="border-rose/20 bg-gradient-to-br from-rose/[0.04] to-transparent">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xxs font-semibold uppercase tracking-eyebrow text-rose">{r.cadence} · {r.audience}</p>
              <StatusBadge tone={scoped ? "rose" : "neutral"} dot={false}>
                <Globe2 className="mr-1 h-3 w-3" /> {scope}
              </StatusBadge>
            </div>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink">{r.summary}</p>
            {scoped && (
              <p className="mt-1.5 text-xxs text-ink-faint">
                Scoped to the active filters. Figures below are period aggregates shown for context.
              </p>
            )}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button variant="ghost" size="sm"><Download className="h-3.5 w-3.5" /> Export</Button>
            <Button variant="primary" size="sm"><Share2 className="h-3.5 w-3.5" /> Share</Button>
          </div>
        </div>
      </Panel>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {r.metrics.map((m) => (
          <div key={m.label} className="rounded-2xl border border-border bg-surface p-4 shadow-card">
            <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{m.label}</p>
            <p className="mt-1 font-mono text-xl font-semibold text-ink tnum">{m.value}</p>
          </div>
        ))}
      </div>

      {/* What changed / risks / next */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel>
          <PanelHeader title="What changed" action={<TrendingUp className="h-4 w-4 text-success" />} />
          <ul className="space-y-2">
            {r.changed.map((c) => (
              <li key={c} className="flex gap-2 text-sm text-ink-muted"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-success" />{c}</li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader title="Risks & blockers" action={<AlertTriangle className="h-4 w-4 text-warning" />} />
          <ul className="space-y-2">
            {r.risks.map((c) => (
              <li key={c} className="flex gap-2 text-sm text-ink-muted"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warning" />{c}</li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader title="Next actions" action={<ArrowRight className="h-4 w-4 text-rose" />} />
          <ul className="space-y-2">
            {r.next.map((c) => (
              <li key={c} className="flex gap-2 text-sm text-ink-muted"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose" />{c}</li>
            ))}
          </ul>
        </Panel>
      </div>

      <p className="flex items-center gap-1.5 text-xxs text-ink-faint"><StatusBadge tone="info" dot={false}>Auto</StatusBadge> Generated automatically · export & share coming soon.</p>
    </div>
  );
}
