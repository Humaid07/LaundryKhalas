"use client";

import { useMemo, useState } from "react";
import { Info, ShieldCheck } from "lucide-react";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList,
  EmptyState, SnapshotBadge, type MinimalKpi, type WorkflowTab,
} from "@/components/dashboard/minimal";
import {
  complianceQueue, complianceTone, getPartnerIdByName,
} from "@/lib/dashboard/partner-acquisition-data";

/**
 * Facility compliance queue — trade license, documents, agreement and onboarding
 * checklist for partner facilities. Relocated from Partner Acquisition so it lives
 * alongside facility management. Status-only view: no document contents or account
 * numbers are stored (privacy). Data comes from the shared partner-acquisition
 * dataset; links still deep-link to the partner pipeline record.
 */

type CompTabId = "all" | "in-review" | "docs-pending" | "flagged" | "passed";
const COMP_TABS: { id: CompTabId; label: string; match: (s: string) => boolean }[] = [
  { id: "all", label: "All", match: () => true },
  { id: "in-review", label: "In review", match: (s) => s === "In Review" },
  { id: "docs-pending", label: "Docs pending", match: (s) => s === "Docs Pending" },
  { id: "flagged", label: "Flagged", match: (s) => s === "Flagged" },
  { id: "passed", label: "Passed", match: (s) => s === "Passed" },
];
const num = (n: number) => String(n);

export function FacilityCompliance() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<CompTabId>("all");
  const base = useMemo(() => applyGlobalFilters(complianceQueue, filters), [filters]);
  const matcher = COMP_TABS.find((t) => t.id === tab)!.match;
  const rows = base.filter((c) => matcher(c.status));

  const kpis: MinimalKpi[] = [
    { label: "Open reviews", value: num(base.filter((c) => c.status !== "Passed").length) },
    { label: "Docs pending", value: num(base.filter((c) => c.status === "Docs Pending").length), tone: "warning" },
    { label: "Flagged", value: num(base.filter((c) => c.status === "Flagged").length), tone: "danger" },
    { label: "Passed", value: num(base.filter((c) => c.status === "Passed").length), tone: "success" },
  ];
  const tabs: WorkflowTab[] = COMP_TABS.map((t) => ({
    id: t.id, label: t.label, count: base.filter((c) => t.match(c.status)).length,
  }));

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs leading-relaxed text-ink-muted">
          <span className="font-semibold text-ink">Status-only view.</span> Trade licenses, bank details and
          documents are represented as states — no document contents or account numbers are stored.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as CompTabId)} />
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      {rows.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="No compliance records in this view"
          description="No partners match this status and the active filters."
        />
      ) : (
        <RecordList>
          {rows.map((c) => {
            const leadId = getPartnerIdByName(c.partner);
            return (
              <CompactRecordCard
                key={c.partner}
                title={c.partner}
                status={{ label: c.status, tone: complianceTone[c.status] }}
                fields={[
                  { label: "Country", value: c.country },
                  { label: "Pending docs", value: String(c.pending) },
                  { label: "Agreement", value: c.agreement },
                ]}
                href={leadId ? `/partner-acquisition/pipeline/${leadId}` : undefined}
              />
            );
          })}
        </RecordList>
      )}
    </div>
  );
}
