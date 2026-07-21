"use client";

import {
  SearchX,
  CalendarClock,
  ShieldCheck,
  Globe2,
  Gauge,
  Eye,
  UserPlus,
  ArrowRightLeft,
  Info,
  StickyNote,
  CheckCircle2,
  XCircle,
  Users,
  Target,
  Briefcase,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { AreaTrend, BarSeries, DonutChart } from "@/components/dashboard/charts";
import { LocalFilterBar, useLocalFilters, matchesLocal, type LocalFilterDef } from "@/components/dashboard/ui/LocalFilters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, getFilteredSummary, activeFilterCount } from "@/lib/dashboard/filters";
import { CHART } from "@/lib/dashboard/chart-theme";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { cn } from "@/lib/utils";
import {
  roleCards,
  roleStatusTone,
  partnerKpis,
  partners,
  stageTone,
  complianceTone,
  marketIntel,
  readinessTone,
  outreach,
  meetings,
  meetingStatusTone,
  complianceQueue,
  docStateTone,
  regionalCoverage,
  coverageStatusTone,
  performancePreview,
  leadsByRegion,
  pipelineByStage,
  scoreDistribution,
  meetingsOverTime,
  partnerTypeBreakdown,
  complianceBreakdown,
  partnerActivity,
  PARTNER_TYPES,
  PIPELINE_STAGES,
  REGIONS_PA,
  PARTNER_OWNERS,
  PARTNER_ACTIONS,
  type Partner,
  type MarketRow,
  type OutreachRow,
  type MeetingRow,
  type ComplianceRow,
  type CoverageRow,
  type PerformancePreviewRow,
  type DocState,
} from "@/lib/dashboard/partner-acquisition-data";

const filteredEmpty = (
  <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />
);

const donutColors = [CHART.rose, CHART.plum, CHART.teal, CHART.amber, CHART.sky, CHART.slate, "rgb(var(--ink-faint))", "rgb(var(--c-plum) / 0.6)"];

/** Header row with an "Overall snapshot" badge for aggregate KPI/chart blocks
 *  that are not recomputed per filter (pipeline/compliance/coverage rollups). */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} />
    </div>
  );
}

function scoreTone(n: number) {
  return n >= 80 ? "success" : n >= 65 ? "rose" : n >= 45 ? "warning" : "neutral";
}

/* --------------------------------- Role cards ------------------------------- */

function RoleCards() {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {roleCards.map((r) => (
        <div key={r.role} className="flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-300 hover:-translate-y-0.5 hover:shadow-raised">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose/12 font-display text-sm font-bold text-rose">{r.initials}</span>
              <div className="min-w-0">
                <h4 className="text-sm font-semibold leading-tight text-ink">{r.role}</h4>
                <p className="text-xxs text-ink-faint">{r.owner}</p>
              </div>
            </div>
            <StatusBadge tone={roleStatusTone[r.status]} dot={false}>{r.status}</StatusBadge>
          </div>
          <div className="mt-3 flex items-start gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1.5">
            <Globe2 className="mt-0.5 h-3 w-3 shrink-0 text-ink-faint" />
            <p className="text-xxs leading-snug text-ink-muted">{r.region}</p>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
            <Meta label="Pipeline" value={String(r.pipeline)} />
            <Meta label="Active tasks" value={String(r.activeTasks)} />
            <Meta label="Meetings / wk" value={String(r.meetingsThisWeek)} />
            <Meta label="Target" value={r.targets} />
          </div>
          <p className="mt-3 border-t border-border pt-3 text-xxs leading-relaxed text-ink-muted">{r.responsibility}</p>
        </div>
      ))}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <p className="mt-0.5 truncate font-mono text-sm font-medium text-ink tnum">{value}</p>
    </div>
  );
}

/* ------------------------------ Partner pipeline ---------------------------- */

const pipelineCols: Column<Partner>[] = [
  { key: "id", header: "Partner ID", primary: true, cell: (p) => <span className="font-mono text-xs font-semibold text-ink">{p.id}</span> },
  { key: "name", header: "Partner Name", cell: (p) => <span className="whitespace-nowrap font-medium text-ink">{p.name}</span> },
  { key: "type", header: "Type", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.type}</span> },
  { key: "region", header: "Region", cell: (p) => <span className="text-xs text-ink-muted">{p.region}</span> },
  { key: "country", header: "Country", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.country}</span> },
  { key: "city", header: "City", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.city}</span> },
  { key: "owner", header: "Owner", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.owner}</span> },
  { key: "stage", header: "Stage", cell: (p) => <StatusBadge tone={stageTone[p.stage]}>{p.stage}</StatusBadge> },
  { key: "score", header: "Score", align: "right", cell: (p) => <StatusBadge tone={scoreTone(p.score)} dot={false}>{p.score}</StatusBadge> },
  { key: "last", header: "Last Contact", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.lastContact === "—" ? "—" : formatRelativeTime(p.lastContact)}</span> },
  { key: "next", header: "Next Step", cell: (p) => <span className="text-xs text-ink-faint">{p.nextStep}</span> },
  { key: "compliance", header: "Compliance", cell: (p) => <StatusBadge tone={complianceTone[p.compliance]} dot={false}>{p.compliance}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary"><Eye className="h-3.5 w-3.5" /> View</Button> },
];

function PipelineTab({ rows }: { rows: Partner[] }) {
  const filterDefs: LocalFilterDef[] = [
    { key: "region", label: "Region", options: REGIONS_PA },
    { key: "type", label: "Partner type", options: PARTNER_TYPES },
    { key: "owner", label: "Owner", options: PARTNER_OWNERS },
    { key: "stage", label: "Stage", options: PIPELINE_STAGES },
  ];
  const { filters } = useFilters();
  const lf = useLocalFilters(filterDefs);
  // Global geo/date filters apply first, then the section's local type/owner/stage filters.
  const globalRows = applyGlobalFilters(rows, filters);
  const filtered = globalRows.filter((p) => matchesLocal(p, lf.values, (row, key) => (row as unknown as Record<string, string>)[key]));

  return (
    <Panel padded={false}>
      <PanelHeader title="Partner pipeline" subtitle={`${filtered.length} of ${partners.length} partners · all stages`} className="p-4" action={<StatusBadge tone="rose">{filtered.filter((p) => p.stage === "Active Partner").length} active</StatusBadge>} />
      <div className="border-b border-border px-4 pb-3">
        <LocalFilterBar defs={filterDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
      </div>
      <div className="px-4 pb-4 pt-4">
        <DataTable columns={pipelineCols} rows={filtered} rowKey={(p) => p.id} empty={filteredEmpty} onRowLabel={(p) => <StatusBadge tone={stageTone[p.stage]}>{p.stage}</StatusBadge>} />
      </div>
      <div className="flex flex-wrap gap-1.5 border-t border-border px-4 py-3">
        {PARTNER_ACTIONS.map((a) => (
          <span key={a} className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xxs font-medium text-ink-muted">{a}</span>
        ))}
      </div>
    </Panel>
  );
}

/* ----------------------------- Market intelligence -------------------------- */

const marketCols: Column<MarketRow>[] = [
  { key: "country", header: "Country", primary: true, cell: (m) => <span className="font-medium text-ink">{m.country}</span> },
  { key: "city", header: "City", cell: (m) => <span className="whitespace-nowrap text-ink-muted">{m.city}</span> },
  { key: "opp", header: "Opportunity", cell: (m) => (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/8"><div className={cn("h-full rounded-full", m.opportunity >= 85 ? "bg-success" : m.opportunity >= 70 ? "bg-rose" : "bg-warning")} style={{ width: `${m.opportunity}%` }} /></div>
      <span className="font-mono text-xs text-ink tnum">{m.opportunity}</span>
    </div>
  ) },
  { key: "demand", header: "Demand", cell: (m) => <span className="whitespace-nowrap text-xs text-ink-muted">{m.demand}</span> },
  { key: "supply", header: "Supply", cell: (m) => <span className="whitespace-nowrap text-xs text-ink-muted">{m.supply}</span> },
  { key: "competitors", header: "Competitors", align: "right", cell: (m) => <span className="font-mono text-sm text-ink tnum">{m.competitors}</span> },
  { key: "category", header: "Suggested Category", cell: (m) => <span className="whitespace-nowrap text-xs text-ink-muted">{m.suggestedCategory}</span> },
  { key: "readiness", header: "Readiness", cell: (m) => <StatusBadge tone={readinessTone[m.readiness]}>{m.readiness}</StatusBadge> },
];

function MarketTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(marketIntel, filters);
  const summary = getFilteredSummary(marketIntel, filters);
  const topCities = [...rows].sort((a, b) => b.opportunity - a.opportunity).slice(0, 5);
  const readinessData = rows.map((m) => ({ label: m.city, value: m.opportunity }));
  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="Market intelligence" subtitle={`${summary.shown} of ${summary.total} cities · opportunity, demand vs supply and competitor coverage`} className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={marketCols} rows={rows} rowKey={(m) => m.city} empty={filteredEmpty} onRowLabel={(m) => <StatusBadge tone={readinessTone[m.readiness]}>{m.readiness}</StatusBadge>} />
        </div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Market readiness by city" subtitle="Opportunity score 0–100">
          {readinessData.length ? <BarSeries data={readinessData} horizontal colorByIndex height={220} /> : filteredEmpty}
        </ChartCard>
        <Panel>
          <PanelHeader title="Suggested target cities" subtitle="Ranked by opportunity" />
          {topCities.length === 0 ? (
            filteredEmpty
          ) : (
            <ul className="space-y-2">
              {topCities.map((m, i) => (
                <li key={m.city} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 p-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose/12 text-xxs font-bold text-rose">{i + 1}</span>
                    <div>
                      <p className="text-sm font-medium text-ink">{m.city}, {m.country}</p>
                      <p className="text-xxs text-ink-faint">{m.suggestedCategory}</p>
                    </div>
                  </div>
                  <StatusBadge tone={readinessTone[m.readiness]} dot={false}>{m.readiness}</StatusBadge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------ Outreach tracker ---------------------------- */

const outreachCols: Column<OutreachRow>[] = [
  { key: "region", header: "Region", primary: true, cell: (o) => <span className="font-medium text-ink">{o.region}</span> },
  { key: "sent", header: "Outreach Sent", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{o.sent}</span> },
  { key: "replies", header: "Replies", align: "right", cell: (o) => <span className="font-mono text-sm text-ink-muted tnum">{o.replies}</span> },
  { key: "meetings", header: "Meetings Booked", align: "right", cell: (o) => <span className="font-mono text-sm text-ink-muted tnum">{o.meetings}</span> },
  { key: "followups", header: "Follow-ups Due", align: "right", cell: (o) => <span className={cn("font-mono text-sm tnum", o.followupsDue > 0 ? "text-warning" : "text-ink-faint")}>{o.followupsDue}</span> },
  { key: "rate", header: "Response Rate", cell: (o) => (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/8"><div className={cn("h-full rounded-full", o.responseRate >= 40 ? "bg-success" : o.responseRate >= 28 ? "bg-rose" : "bg-warning")} style={{ width: `${o.responseRate}%` }} /></div>
      <span className="font-mono text-xs text-ink-muted tnum">{o.responseRate.toFixed(1)}%</span>
    </div>
  ) },
];

function OutreachTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(outreach, filters);
  const summary = getFilteredSummary(outreach, filters);
  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="Outreach tracker" subtitle={`${summary.shown} of ${summary.total} regions · outreach performance`} className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={outreachCols} rows={rows} rowKey={(o) => o.region} empty={filteredEmpty} />
        </div>
      </Panel>
      <ChartCard title="Outreach conversion by region" subtitle="Reply rate %">
        {rows.length ? <BarSeries data={rows.map((o) => ({ label: o.region, value: o.responseRate }))} colorByIndex height={220} /> : filteredEmpty}
      </ChartCard>
    </div>
  );
}

/* --------------------------- Meetings & follow-ups -------------------------- */

const meetingCols: Column<MeetingRow>[] = [
  { key: "id", header: "Meeting", primary: true, cell: (m) => <span className="font-mono text-xs font-semibold text-ink">{m.id}</span> },
  { key: "partner", header: "Partner", cell: (m) => <span className="whitespace-nowrap font-medium text-ink">{m.partner}</span> },
  { key: "owner", header: "Owner", cell: (m) => <span className="whitespace-nowrap text-xs text-ink-muted">{m.owner}</span> },
  { key: "datetime", header: "Date / Time", cell: (m) => <span className="whitespace-nowrap text-xs text-ink-muted">{new Date(m.datetime).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</span> },
  { key: "type", header: "Type", cell: (m) => <StatusBadge tone="neutral" dot={false}>{m.type}</StatusBadge> },
  { key: "next", header: "Next Action", cell: (m) => <span className="text-xs text-ink-faint">{m.nextAction}</span> },
  { key: "status", header: "Status", cell: (m) => <StatusBadge tone={meetingStatusTone[m.status]}>{m.status}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Open</Button> },
];

function MeetingsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(meetings, filters);
  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="Meetings & follow-ups" subtitle={`${rows.length} of ${meetings.length} meetings · calendar view`} className="p-4" action={<StatusBadge tone="plum">{rows.filter((m) => m.status !== "Done").length} upcoming</StatusBadge>} />
        <div className="px-4 pb-4">
          <DataTable columns={meetingCols} rows={rows} rowKey={(m) => m.id} empty={filteredEmpty} onRowLabel={(m) => <StatusBadge tone={meetingStatusTone[m.status]}>{m.status}</StatusBadge>} />
        </div>
      </Panel>
      <ChartCard title="Meetings scheduled over time" subtitle="Last 6 weeks" action={<SnapshotBadge active={activeFilterCount(filters) > 0} />}>
        <AreaTrend data={meetingsOverTime} series={[{ key: "Meetings", color: CHART.plum }]} height={200} />
      </ChartCard>
    </div>
  );
}

/* ------------------------------ Compliance queue ---------------------------- */

function DocCell({ state }: { state: DocState }) {
  return <StatusBadge tone={docStateTone[state]} dot={false}>{state}</StatusBadge>;
}

const complianceCols: Column<ComplianceRow>[] = [
  { key: "partner", header: "Partner", primary: true, cell: (c) => <span className="whitespace-nowrap font-medium text-ink">{c.partner}</span> },
  { key: "country", header: "Country", cell: (c) => <span className="text-xs text-ink-muted">{c.country}</span> },
  { key: "license", header: "Trade License", cell: (c) => <DocCell state={c.tradeLicense} /> },
  { key: "bank", header: "Bank / Payout", cell: (c) => <DocCell state={c.bankPayout} /> },
  { key: "quality", header: "Quality Checklist", cell: (c) => <DocCell state={c.qualityChecklist} /> },
  { key: "agreement", header: "Agreement", cell: (c) => <DocCell state={c.agreement} /> },
  { key: "insurance", header: "Insurance / Docs", cell: (c) => <DocCell state={c.insurance} /> },
  { key: "pending", header: "Pending", align: "right", cell: (c) => <span className={cn("font-mono text-sm tnum", c.pending > 0 ? "text-warning" : "text-ink-faint")}>{c.pending}</span> },
  { key: "status", header: "Status", cell: (c) => <StatusBadge tone={complianceTone[c.status]}>{c.status}</StatusBadge> },
];

function ComplianceTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(complianceQueue, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Compliance queue" subtitle="Document status only — no files or private data stored" className="p-4" action={<StatusBadge tone="warning">{rows.filter((c) => c.status !== "Passed").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={complianceCols} rows={rows} rowKey={(c) => c.partner} empty={filteredEmpty} onRowLabel={(c) => <StatusBadge tone={complianceTone[c.status]}>{c.status}</StatusBadge>} />
      </div>
      <p className="flex items-center gap-1.5 border-t border-border px-4 py-3 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Status-only view. Trade licenses, bank details and documents are represented as states — no document contents or account numbers are shown.</p>
    </Panel>
  );
}

/* ------------------------------ Regional coverage --------------------------- */

const coverageCols: Column<CoverageRow>[] = [
  { key: "region", header: "Region / Market", primary: true, cell: (c) => <span className="font-medium text-ink">{c.region}</span> },
  { key: "active", header: "Active Partners", align: "right", cell: (c) => <span className="font-mono text-sm text-ink tnum">{c.activePartners}</span> },
  { key: "pipeline", header: "In Pipeline", align: "right", cell: (c) => <span className="font-mono text-sm text-ink-muted tnum">{c.pipeline}</span> },
  { key: "coverage", header: "Market Coverage", cell: (c) => (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/8"><div className="h-full rounded-full bg-rose" style={{ width: `${(c.covered / c.targetMarkets) * 100}%` }} /></div>
      <span className="font-mono text-xs text-ink-muted tnum">{c.covered}/{c.targetMarkets}</span>
    </div>
  ) },
  { key: "status", header: "Status", cell: (c) => <StatusBadge tone={coverageStatusTone[c.status]}>{c.status}</StatusBadge> },
];

function CoverageTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(regionalCoverage, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Regional coverage" subtitle="MENA · Asia · Europe · Americas · GCC and key markets" className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={coverageCols} rows={rows} rowKey={(c) => c.region} empty={filteredEmpty} onRowLabel={(c) => <StatusBadge tone={coverageStatusTone[c.status]}>{c.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* -------------------------- Partner performance preview --------------------- */

const perfCols: Column<PerformancePreviewRow>[] = [
  { key: "partner", header: "Partner", primary: true, cell: (p) => <span className="whitespace-nowrap font-medium text-ink">{p.partner}</span> },
  { key: "city", header: "City", cell: (p) => <span className="text-xs text-ink-muted">{p.city}</span> },
  { key: "orders", header: "Orders Handled", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.ordersHandled}</span> },
  { key: "turnaround", header: "Avg Turnaround", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.avgTurnaround}</span> },
  { key: "quality", header: "Quality Score", align: "right", cell: (p) => <StatusBadge tone={scoreTone(p.qualityScore)} dot={false}>{p.qualityScore}</StatusBadge> },
  { key: "complaint", header: "Complaint Rate", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.complaintRate.toFixed(1)}%</span> },
  { key: "revenue", header: "Revenue Share", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.revenueShare.toFixed(1)}%</span> },
];

function PerformanceTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(performancePreview, filters);
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <div>
          <p className="text-xs font-semibold text-ink">Preview — populated once partners are live</p>
          <p className="text-xxs text-ink-muted">Full partner performance (orders, turnaround, quality, complaints, revenue) will stream in from Operations once onboarded partners handle live volume. Two onboarded partners shown as a preview.</p>
        </div>
      </div>
      <Panel padded={false}>
        <PanelHeader title="Partner performance preview" subtitle="Onboarded partners only" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={perfCols} rows={rows} rowKey={(p) => p.partner} empty={<EmptyState icon={Gauge} title="No onboarded partners yet" description="Performance appears here once partners go live." />} />
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------- Team & ownership --------------------------- */

function TeamSection() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Team & ownership" />
      <div className="grid gap-4 xl:grid-cols-3">
      <div className="min-w-0 xl:col-span-2">
        <RoleCards />
      </div>
      <aside className="space-y-4">
        <div className="flex items-start gap-2.5 rounded-xl border border-warning/25 bg-warning/8 p-3">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div>
            <p className="text-xs font-semibold text-ink">Business data</p>
            <p className="text-xxs text-ink-muted">No live CRM or outreach tools connected. Only business-level partner data — no private personal emails or phone numbers in tables.</p>
          </div>
        </div>
        <Panel>
          <PanelHeader title="Partnership activity" subtitle="Latest pipeline events" />
          <ActivityTimeline events={partnerActivity} />
        </Panel>
        <Panel>
          <PanelHeader title="Quick actions" />
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Add Partner Lead", icon: UserPlus },
              { label: "Assign Owner", icon: Users },
              { label: "Move Stage", icon: ArrowRightLeft },
              { label: "Schedule Meeting", icon: CalendarClock },
              { label: "Request Compliance", icon: ShieldCheck },
              { label: "Add Note", icon: StickyNote },
              { label: "Mark Onboarded", icon: CheckCircle2 },
              { label: "Reject Lead", icon: XCircle },
              { label: "New Market Report", icon: Target },
              { label: "View B2B Partners", icon: Briefcase },
            ].map((a) => (
              <button key={a.label} type="button" className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-2.5 py-2 text-left text-xs font-medium text-ink transition-colors hover:border-rose/40">
                <a.icon className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                <span className="truncate">{a.label}</span>
              </button>
            ))}
          </div>
        </Panel>
      </aside>
      </div>
    </div>
  );
}

/* -------------------------------- Pipeline section -------------------------- */

function PipelineSection() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="Pipeline snapshot" />
      <StatGrid stats={partnerKpis} cols="auto" />
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Pipeline by stage" subtitle="Partners per stage" className="lg:col-span-2">
          <BarSeries data={pipelineByStage} color={CHART.rose} height={220} />
        </ChartCard>
        <ChartCard title="Partner type breakdown" subtitle="Share of pipeline">
          <DonutChart data={partnerTypeBreakdown} colors={donutColors} centerValue="184" centerLabel="Leads" height={200} />
        </ChartCard>
      </div>
      <PipelineTab rows={partners} />
    </div>
  );
}

/* ------------------------------ Compliance section -------------------------- */

function ComplianceSection() {
  return (
    <div className="space-y-4">
      <ComplianceTab />
      <SnapshotRow label="Compliance rollup" />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Compliance status breakdown" subtitle="Across all partners">
          <DonutChart data={complianceBreakdown} colors={[CHART.teal, CHART.sky, CHART.amber, "rgb(var(--ink-faint))", CHART.rose]} centerValue="58" centerLabel="Partners" height={220} />
        </ChartCard>
        <ChartCard title="Partner score distribution" subtitle="Count by score band">
          <BarSeries data={scoreDistribution} color={CHART.teal} height={220} />
        </ChartCard>
      </div>
    </div>
  );
}

/* ------------------------------- Coverage section --------------------------- */

function CoverageSection() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Coverage rollup" />
      <ChartCard title="Partner leads by region" subtitle="Total leads">
        <BarSeries data={leadsByRegion} colorByIndex height={200} />
      </ChartCard>
      <CoverageTab />
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Partner Acquisition subsection by slug (see lib/dashboard/sections.ts). */
export function PartnerSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "team": return <TeamSection />;
    case "pipeline": return <PipelineSection />;
    case "market-intelligence": return <MarketTab />;
    case "outreach": return <OutreachTab />;
    case "meetings": return <MeetingsTab />;
    case "compliance-queue": return <ComplianceSection />;
    case "regional-coverage": return <CoverageSection />;
    case "performance-preview": return <PerformanceTab />;
    default: return <TeamSection />;
  }
}
