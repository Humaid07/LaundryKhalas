"use client";

import { Sparkles, AlertTriangle, TrendingUp, TrendingDown, Minus, FileText, SearchX } from "lucide-react";
import { SectionTitle } from "@/components/dashboard/shell/PageHeader";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { AreaTrend, BarSeries, DonutChart } from "@/components/dashboard/charts";
import { AgentStatusCard } from "@/components/dashboard/widgets";
import { toneDot } from "@/components/dashboard/ui/tones";
import { CHART } from "@/lib/dashboard/chart-theme";
import { priorityTone } from "@/lib/dashboard/status-maps";
import { activeFilterCount } from "@/lib/dashboard/filters";
import {
  seoAgents,
  seoKpis,
  gscPerformance,
  indexedVsNon,
  contentPipeline,
  seoTasks,
  seoBrief,
} from "@/lib/dashboard/mock-data";
import {
  gscPages,
  indexingQueue,
  indexStateTone,
  hyperlocalPages,
  hyperlocalStatusTone,
  techSeoIssues,
  techSeoSeverityTone,
  competitors,
  aiSearch,
  aiPresenceTone,
  pagesGainingLosing,
  type GscPage,
  type IndexRow,
  type HyperlocalPage,
  type TechSeoIssue,
  type AiSearchRow,
} from "@/lib/dashboard/seo-data";
import { applyGlobalFilters } from "@/lib/dashboard/filters";
import type { SeoTask } from "@/lib/dashboard/types";
import { cn } from "@/lib/utils";

/* ------------------------------- shared table ------------------------------- */

/** Shared empty state for lists narrowed to nothing by the global filters. */
const noMatchState = (
  <EmptyState
    icon={SearchX}
    title="No records match the selected filters"
    description="Try clearing a filter to see more."
  />
);

/** Header row flagging aggregate/site-wide SEO views that are not geo-filtered. */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} label="Global / site-wide" />
    </div>
  );
}

const taskCols: Column<SeoTask>[] = [
  { key: "task", header: "Task", primary: true, cell: (t) => <span className="text-ink">{t.task}</span> },
  { key: "agent", header: "Agent", cell: (t) => <span className="text-ink-muted">{t.agent}</span> },
  { key: "priority", header: "Priority", cell: (t) => <StatusBadge tone={priorityTone[t.priority]}>{t.priority}</StatusBadge> },
  { key: "url", header: "Page / URL", cell: (t) => <span className="font-mono text-xs text-ink-muted">{t.url}</span> },
  { key: "status", header: "Status", cell: (t) => <StatusBadge tone={t.status === "Done" ? "success" : t.status === "Needs Review" ? "warning" : "info"}>{t.status}</StatusBadge> },
  { key: "action", header: "Suggested action", cell: (t) => <span className="text-xs text-ink-muted">{t.suggestedAction}</span> },
  { key: "approve", header: "", align: "right", cell: (t) => (t.approvalRequired ? <Button size="sm" variant="primary">Review</Button> : <Button size="sm" variant="ghost">Run</Button>) },
];

/* -------------------------------- Overview ---------------------------------- */

function BriefPanel() {
  return (
    <Panel className="border-rose/20 bg-gradient-to-br from-rose/[0.04] to-transparent">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose/12 text-rose"><Sparkles className="h-4 w-4" /></span>
        <div>
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-rose">Daily SEO Brief · {seoBrief.date}</p>
          <h3 className="font-display text-base font-semibold text-ink">{seoBrief.headline}</h3>
        </div>
      </div>
      <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
        {seoBrief.items.map((it) => (
          <li key={it.title} className="flex gap-2.5 rounded-xl border border-border bg-surface p-3">
            <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", toneDot[it.tone])} />
            <div>
              <p className="text-xs font-semibold text-ink">{it.title}</p>
              <p className="text-xs text-ink-muted">{it.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function OverviewSection() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="SEO overview" />
      <BriefPanel />
      <StatGrid stats={seoKpis} cols="auto" />
      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard title="GSC performance" subtitle="Clicks & impressions · 4 weeks" className="xl:col-span-2">
          <AreaTrend data={gscPerformance} series={[{ key: "Impressions", color: CHART.plum }, { key: "Clicks", color: CHART.rose }]} />
        </ChartCard>
        <ChartCard title="Index coverage" subtitle="1,284 known URLs">
          <DonutChart data={indexedVsNon} colors={[CHART.teal, CHART.amber, CHART.slate]} centerValue="94%" centerLabel="Indexed" />
        </ChartCard>
      </div>
    </div>
  );
}

/* ------------------------------- Agent fleet -------------------------------- */

function AgentFleetSection() {
  const needAttention = seoAgents.filter((a) => a.approvalRequired || a.status === "Needs Review").length;
  return (
    <div className="space-y-6">
      <SnapshotRow label="Agent fleet" />
      <SectionTitle title="Agent fleet" description={`${seoAgents.length} agents · ${needAttention} need attention`} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {seoAgents.map((a) => <AgentStatusCard key={a.name} agent={a} />)}
      </div>
      <Panel padded={false}>
        <div className="flex items-center justify-between p-4">
          <PanelHeader title="SEO tasks" subtitle="Prioritised backlog · approval-gated" className="mb-0" />
          <StatusBadge tone="warning"><AlertTriangle className="h-3 w-3" /> {seoTasks.filter((t) => t.approvalRequired).length} need approval</StatusBadge>
        </div>
        <div className="px-4 pb-4">
          <DataTable columns={taskCols} rows={seoTasks} rowKey={(t) => t.id} onRowLabel={(t) => <StatusBadge tone={priorityTone[t.priority]}>{t.priority}</StatusBadge>} />
        </div>
      </Panel>
    </div>
  );
}

/* ----------------------------- GSC performance ------------------------------ */

const gscCols: Column<GscPage>[] = [
  { key: "page", header: "Page", primary: true, cell: (p) => <span className="font-mono text-xs text-ink">{p.page}</span> },
  { key: "clicks", header: "Clicks", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.clicks}</span> },
  { key: "impressions", header: "Impressions", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.impressions.toLocaleString()}</span> },
  { key: "ctr", header: "CTR", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.ctr}%</span> },
  { key: "position", header: "Position", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.position.toFixed(1)}</span> },
  { key: "delta", header: "Δ", align: "right", cell: (p) => <span className={cn("font-mono text-xs tnum", p.delta > 0 ? "text-success" : p.delta < 0 ? "text-danger" : "text-ink-faint")}>{p.delta > 0 ? "+" : ""}{p.delta}</span> },
];

function GscSection() {
  const { filters } = useFilters();
  const pages = applyGlobalFilters(gscPages, filters);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard title="Clicks & impressions" subtitle="Overall · 4 weeks" className="xl:col-span-2">
          <AreaTrend data={gscPerformance} series={[{ key: "Impressions", color: CHART.plum }, { key: "Clicks", color: CHART.rose }]} />
        </ChartCard>
        <ChartCard title="Pages gaining / losing" subtitle="Overall · last 4 weeks">
          <DonutChart data={pagesGainingLosing} colors={[CHART.teal, CHART.slate, CHART.danger]} centerValue="107" centerLabel="Pages" />
        </ChartCard>
      </div>
      <Panel padded={false}>
        <PanelHeader title="Top pages" subtitle="Clicks, CTR and position" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={gscCols} rows={pages} rowKey={(p) => p.page} empty={noMatchState} />
        </div>
      </Panel>
    </div>
  );
}

/* --------------------------------- Indexing --------------------------------- */

const indexCols: Column<IndexRow>[] = [
  { key: "url", header: "URL", primary: true, cell: (r) => <span className="font-mono text-xs text-ink">{r.url}</span> },
  { key: "state", header: "State", cell: (r) => <StatusBadge tone={indexStateTone[r.state]}>{r.state}</StatusBadge> },
  { key: "checked", header: "Last Checked", cell: (r) => <span className="whitespace-nowrap text-xs text-ink-muted">{r.lastChecked}</span> },
  { key: "action", header: "Action", cell: (r) => <span className="text-xs text-ink-faint">{r.action}</span> },
  { key: "btn", header: "", align: "right", cell: (r) => (r.state === "Failed" ? <Button size="sm" variant="primary">Resubmit</Button> : <Button size="sm" variant="ghost">View</Button>) },
];

function IndexingSection() {
  const { filters } = useFilters();
  const queue = applyGlobalFilters(indexingQueue, filters);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Index coverage" subtitle="Overall · 1,284 known URLs">
          <DonutChart data={indexedVsNon} colors={[CHART.teal, CHART.amber, CHART.slate]} centerValue="94%" centerLabel="Indexed" height={220} />
        </ChartCard>
        <Panel className="lg:col-span-2" padded={false}>
          <PanelHeader title="Indexing queue" subtitle="Submitted, crawled & failed URLs" className="p-4" action={<StatusBadge tone="danger">{queue.filter((r) => r.state === "Failed").length} failed</StatusBadge>} />
          <div className="px-4 pb-4">
            <DataTable columns={indexCols} rows={queue} rowKey={(r) => r.url} onRowLabel={(r) => <StatusBadge tone={indexStateTone[r.state]}>{r.state}</StatusBadge>} empty={noMatchState} />
          </div>
        </Panel>
      </div>
    </div>
  );
}

/* ----------------------------- Content pipeline ----------------------------- */

function ContentPipelineSection() {
  const { filters } = useFilters();
  const tasks = applyGlobalFilters(seoTasks, filters);
  return (
    <div className="space-y-4">
      <ChartCard title="Content pipeline" subtitle="Overall · articles & area pages by stage">
        <BarSeries data={contentPipeline} colorByIndex height={230} />
      </ChartCard>
      <Panel padded={false}>
        <PanelHeader title="Content & linking tasks" subtitle="Approval-gated" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={taskCols} rows={tasks} rowKey={(t) => t.id} onRowLabel={(t) => <StatusBadge tone={priorityTone[t.priority]}>{t.priority}</StatusBadge>} empty={noMatchState} />
        </div>
      </Panel>
    </div>
  );
}

/* ----------------------------- Hyperlocal pages ----------------------------- */

const hyperCols: Column<HyperlocalPage>[] = [
  { key: "area", header: "Area Page", primary: true, cell: (p) => <span className="font-medium text-ink">{p.area}</span> },
  { key: "city", header: "City", cell: (p) => <span className="text-xs text-ink-muted">{p.city}</span> },
  { key: "status", header: "Status", cell: (p) => <StatusBadge tone={hyperlocalStatusTone[p.status]}>{p.status}</StatusBadge> },
  { key: "words", header: "Words", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.wordCount}</span> },
  { key: "dup", header: "Duplicate", align: "right", cell: (p) => <span className={cn("font-mono text-xs tnum", p.duplicateScore > 30 ? "text-danger" : p.duplicateScore > 10 ? "text-warning" : "text-ink-muted")}>{p.duplicateScore}%</span> },
  { key: "btn", header: "", align: "right", cell: (p) => (p.status === "Awaiting Approval" ? <Button size="sm" variant="primary">Review</Button> : <Button size="sm" variant="ghost">Open</Button>) },
];

function HyperlocalSection() {
  const { filters } = useFilters();
  const pages = applyGlobalFilters(hyperlocalPages, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Hyperlocal area pages" subtitle="Area/market pages with duplicate checks" className="p-4" action={<StatusBadge tone="danger">{pages.filter((p) => p.status === "Duplicate Risk").length} duplicate risk</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={hyperCols} rows={pages} rowKey={(p) => p.area} onRowLabel={(p) => <StatusBadge tone={hyperlocalStatusTone[p.status]}>{p.status}</StatusBadge>} empty={noMatchState} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Technical SEO ------------------------------ */

const techCols: Column<TechSeoIssue>[] = [
  { key: "issue", header: "Issue", primary: true, cell: (t) => <span className="text-ink">{t.issue}</span> },
  { key: "type", header: "Type", cell: (t) => <StatusBadge tone="neutral" dot={false}>{t.type}</StatusBadge> },
  { key: "affected", header: "Affected", align: "right", cell: (t) => <span className="font-mono text-sm text-ink tnum">{t.affected}</span> },
  { key: "severity", header: "Severity", cell: (t) => <StatusBadge tone={techSeoSeverityTone[t.severity]}>{t.severity}</StatusBadge> },
  { key: "status", header: "Status", cell: (t) => <StatusBadge tone={t.status === "Resolved" ? "success" : t.status === "Monitoring" ? "info" : "warning"}>{t.status}</StatusBadge> },
  { key: "btn", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Fix</Button> },
];

function TechnicalSeoSection() {
  const { filters } = useFilters();
  // Site-wide issues are tagged scope:"global" and stay visible under geo filters;
  // market-specific issues (e.g. a Dubai cannibalization) carry a city.
  const issues = applyGlobalFilters(techSeoIssues, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Technical SEO" subtitle="Crawl, cannibalization, decay & internal linking" className="p-4" action={<StatusBadge tone="warning">{issues.filter((t) => t.status !== "Resolved").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={techCols} rows={issues} rowKey={(t) => t.issue} onRowLabel={(t) => <StatusBadge tone={techSeoSeverityTone[t.severity]}>{t.severity}</StatusBadge>} empty={noMatchState} />
      </div>
    </Panel>
  );
}

/* -------------------------------- Competitors ------------------------------- */

function CompetitorsSection() {
  const { filters } = useFilters();
  const Icon = { up: TrendingUp, down: TrendingDown, flat: Minus };
  // Domain-wide signals (backlinks/PR) are scope:"global"; ranking/page moves
  // tied to a market carry a city.
  const rows = applyGlobalFilters(competitors, filters);
  return (
    <Panel>
      <PanelHeader title="Competitor monitor" subtitle="Ranking movement, new pages and backlinks" />
      {rows.length === 0 ? (
        noMatchState
      ) : (
      <ul className="divide-y divide-border">
        {rows.map((c) => {
          const M = Icon[c.movement];
          return (
            <li key={c.name} className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3">
                <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg", c.movement === "up" ? "bg-success/12 text-success" : c.movement === "down" ? "bg-danger/12 text-danger" : "bg-ink/8 text-ink-muted")}><M className="h-4 w-4" /></span>
                <div>
                  <p className="text-sm font-medium text-ink">{c.name}</p>
                  <p className="text-xxs text-ink-faint">{c.detail}</p>
                </div>
              </div>
              <span className="whitespace-nowrap font-mono text-xs text-ink-muted">{c.change}</span>
            </li>
          );
        })}
      </ul>
      )}
    </Panel>
  );
}

/* --------------------------------- AI search -------------------------------- */

const aiCols: Column<AiSearchRow>[] = [
  { key: "query", header: "Query", primary: true, cell: (a) => <span className="text-ink">{a.query}</span> },
  { key: "presence", header: "Presence", cell: (a) => <StatusBadge tone={aiPresenceTone[a.presence]}>{a.presence}</StatusBadge> },
  { key: "engine", header: "Engine", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.engine}</span> },
  { key: "opportunity", header: "Opportunity", cell: (a) => <span className="text-xs text-ink-faint">{a.opportunity}</span> },
];

function AiSearchSection() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(aiSearch, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="AI search visibility" subtitle="Answer-engine presence & structured content opportunities" className="p-4" action={<StatusBadge tone="warning">{rows.filter((a) => a.presence === "Absent").length} gaps</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={aiCols} rows={rows} rowKey={(a) => a.query} onRowLabel={(a) => <StatusBadge tone={aiPresenceTone[a.presence]}>{a.presence}</StatusBadge>} empty={noMatchState} />
      </div>
    </Panel>
  );
}

/* ---------------------------------- Reports --------------------------------- */

function ReportsSection() {
  const reports = [
    { name: "Daily SEO Brief", freq: "Daily · 07:00", summary: seoBrief.headline },
    { name: "Weekly SEO Report", freq: "Weekly · Mon", summary: "Ranking movement, clicks & CTR, content shipped, opportunities queued." },
    { name: "Monthly SEO Strategy", freq: "Monthly", summary: "Topical authority progress, hyperlocal coverage and roadmap for next month." },
  ];
  return (
    <div className="space-y-4">
      <SnapshotRow label="SEO reports" />
      <BriefPanel />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {reports.map((r) => (
          <Panel key={r.name} className="flex flex-col">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="font-display text-sm font-semibold text-ink">{r.name}</h4>
                <p className="text-xxs text-ink-faint">{r.freq}</p>
              </div>
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose/10 text-rose"><FileText className="h-4 w-4" /></span>
            </div>
            <p className="mt-3 flex-1 text-xs leading-relaxed text-ink-muted">{r.summary}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button size="sm" variant="ghost">Export</Button>
              <Button size="sm" variant="primary">View</Button>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one SEO Agents subsection by slug (see lib/dashboard/sections.ts). */
export function SeoSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "overview": return <OverviewSection />;
    case "agent-fleet": return <AgentFleetSection />;
    case "gsc-performance": return <GscSection />;
    case "indexing": return <IndexingSection />;
    case "content-pipeline": return <ContentPipelineSection />;
    case "hyperlocal-pages": return <HyperlocalSection />;
    case "technical-seo": return <TechnicalSeoSection />;
    case "competitors": return <CompetitorsSection />;
    case "ai-search": return <AiSearchSection />;
    case "reports": return <ReportsSection />;
    default: return <OverviewSection />;
  }
}
