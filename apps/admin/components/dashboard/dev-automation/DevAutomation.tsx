"use client";

import {
  Activity,
  Bot,
  Globe,
  Plug,
  SearchX,
  ShieldCheck,
  Eye,
  RotateCw,
  Pause,
  Play,
  Settings2,
  UserPlus,
  CirclePlus,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline, ConnectedAppRow, MiniMetric } from "@/components/dashboard/widgets";
import { LocalFilterBar, useLocalFilters, matchesLocal, type LocalFilterDef } from "@/components/dashboard/ui/LocalFilters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { AreaTrend, BarSeries, DonutChart } from "@/components/dashboard/charts";
import { CHART } from "@/lib/dashboard/chart-theme";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { cn } from "@/lib/utils";
import {
  devKpis,
  agentHealth,
  agentStatusToneD,
  techIssues,
  severityTone,
  issueStatusTone,
  apiHealth,
  apiStatusTone,
  jobQueue,
  jobStatusTone,
  llmUsage,
  deployments,
  deployStatusTone,
  buildStatusTone,
  integrations,
  integrationStatusTone,
  logs,
  logSeverityTone,
  liveVsMock,
  issuesByCategory,
  apiLatencyOverTime,
  failedJobsTrend,
  llmCallsByAgent,
  costByAgent,
  uptimeTrend,
  integrationBreakdown,
  devActivity,
  AGENT_CATEGORIES,
  AGENT_STATUSES,
  AGENT_MODES,
  AGENT_OWNERS,
  AGENT_ACTIONS,
  type AgentHealth,
  type TechIssue,
  type ApiHealth,
  type JobRow,
  type LlmUsageRow,
  type DeployRow,
  type LogRow,
} from "@/lib/dashboard/dev-automation-data";

const noMatch = <EmptyState icon={Bot} title="No matches" description="No records match the active filters." />;
const filteredEmpty = (
  <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />
);
const donutColors = [CHART.rose, CHART.plum, CHART.teal, CHART.amber, CHART.sky, CHART.slate];

/**
 * Honest note for the mostly-technical subsections: their rows are tagged
 * `scope: "global"`, so geo filters (Region/Market/City) never hide them. Only
 * the few market/channel-tagged rows respond to the global filter bar.
 */
const globalHint = (
  <p className="flex items-center gap-1.5 border-t border-border px-4 py-2.5 text-xxs text-ink-faint">
    <Globe className="h-3 w-3 shrink-0" /> Global · not geo-filtered — technical items stay visible under geo filters; only market/channel-tagged rows respond.
  </p>
);

/** Header row flagging global/technical Dev views that geo filters don't narrow. */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} label="Global / technical" />
    </div>
  );
}

/* ---------------------------- Automation overview --------------------------- */

function AutomationOverviewTab() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MiniMetric label="Live agents" value="1" tone="success" />
        <MiniMetric label="Staged agents" value="18" tone="info" />
        <MiniMetric label="Active automations" value="11" delta={10} tone="rose" />
        <MiniMetric label="Failed automations" value="4" delta={-2} tone="danger" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Live vs staged agents" subtitle="Agent status split">
          <BarSeries data={liveVsMock} colorByIndex height={200} />
        </ChartCard>
        <ChartCard title="Agent issues by category" subtitle="Open issues">
          <BarSeries data={issuesByCategory} color={CHART.amber} height={200} />
        </ChartCard>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Failed jobs trend" subtitle="Last 7 days">
          <AreaTrend data={failedJobsTrend} series={[{ key: "value", name: "Failed jobs", color: CHART.danger }]} height={180} />
        </ChartCard>
        <ChartCard title="Uptime trend" subtitle="Last 7 days · %">
          <AreaTrend data={uptimeTrend} series={[{ key: "value", name: "Uptime", color: CHART.teal }]} height={180} />
        </ChartCard>
      </div>
    </div>
  );
}

/* ------------------------------- Agent health ------------------------------- */

const agentCols: Column<AgentHealth>[] = [
  { key: "name", header: "Agent", primary: true, cell: (a) => <span className="whitespace-nowrap font-medium text-ink">{a.name}</span> },
  { key: "category", header: "Category", cell: (a) => <span className="text-xs text-ink-muted">{a.category}</span> },
  { key: "status", header: "Status", cell: (a) => <StatusBadge tone={agentStatusToneD[a.status]}>{a.status}</StatusBadge> },
  { key: "mode", header: "Mode", cell: (a) => <StatusBadge tone="neutral" dot={false}>{a.mode}</StatusBadge> },
  { key: "lastRun", header: "Last Run", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.lastRun === "—" ? "—" : formatRelativeTime(a.lastRun)}</span> },
  { key: "nextRun", header: "Next Run", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.nextRun === "—" ? "—" : formatRelativeTime(a.nextRun)}</span> },
  { key: "success", header: "Success", align: "right", cell: (a) => <span className="font-mono text-xs text-ink tnum">{a.successRate ? `${a.successRate}%` : "—"}</span> },
  { key: "latency", header: "Avg Latency", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.avgLatency}</span> },
  { key: "cost", header: "Cost Today", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.costToday ? formatCurrency(a.costToday) : "—"}</span> },
  { key: "issues", header: "Issues", align: "right", cell: (a) => <span className={cn("font-mono text-sm tnum", a.issues > 0 ? "text-warning" : "text-ink-faint")}>{a.issues}</span> },
  { key: "owner", header: "Owner", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.owner}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary"><Eye className="h-3.5 w-3.5" /> Logs</Button> },
];

function AgentHealthTab() {
  const filterDefs: LocalFilterDef[] = [
    { key: "status", label: "Status", options: AGENT_STATUSES },
    { key: "category", label: "Category", options: AGENT_CATEGORIES },
    { key: "mode", label: "Mode", options: AGENT_MODES },
    { key: "owner", label: "Owner", options: AGENT_OWNERS },
  ];
  const lf = useLocalFilters(filterDefs);
  const rows = agentHealth.filter((a) => matchesLocal(a, lf.values, (row, key) => (row as unknown as Record<string, string>)[key]));

  return (
    <Panel padded={false}>
      <PanelHeader title="Agent health" subtitle={`${rows.length} of ${agentHealth.length} agents · status, mode, success rate & cost`} className="p-4" action={<StatusBadge tone="warning">{agentHealth.filter((a) => a.issues > 0).length} with issues</StatusBadge>} />
      <div className="border-b border-border px-4 pb-3">
        <LocalFilterBar defs={filterDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
      </div>
      <div className="px-4 pb-4 pt-4">
        <DataTable columns={agentCols} rows={rows} rowKey={(a) => a.name} empty={noMatch} onRowLabel={(a) => <StatusBadge tone={agentStatusToneD[a.status]}>{a.status}</StatusBadge>} />
      </div>
      <div className="flex flex-wrap gap-1.5 border-t border-border px-4 py-3">
        {AGENT_ACTIONS.map((a) => (
          <span key={a} className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xxs font-medium text-ink-muted">{a}</span>
        ))}
      </div>
    </Panel>
  );
}

/* ------------------------------ Technical issues ---------------------------- */

const issueCols: Column<TechIssue>[] = [
  { key: "id", header: "Issue", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-ink">{i.id}</span> },
  { key: "title", header: "Title", cell: (i) => <span className="text-ink">{i.title}</span> },
  { key: "severity", header: "Severity", cell: (i) => <StatusBadge tone={severityTone[i.severity]}>{i.severity}</StatusBadge> },
  { key: "module", header: "Module", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{i.module}</span> },
  { key: "owner", header: "Owner", cell: (i) => <span className="text-xs text-ink-muted">{i.owner}</span> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={issueStatusTone[i.status]}>{i.status}</StatusBadge> },
  { key: "created", header: "Created", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(i.createdAt)}</span> },
  { key: "updated", header: "Last Update", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(i.lastUpdate)}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Manage</Button> },
];

function TechIssuesTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(techIssues, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Technical issues" subtitle="Known engineering gaps & bugs" className="p-4" action={<StatusBadge tone="warning">{rows.filter((i) => i.status !== "Resolved").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={issueCols} rows={rows} rowKey={(i) => i.id} empty={filteredEmpty} onRowLabel={(i) => <StatusBadge tone={severityTone[i.severity]}>{i.severity}</StatusBadge>} />
      </div>
      {globalHint}
    </Panel>
  );
}

/* ---------------------------- API & webhook health -------------------------- */

const apiCols: Column<ApiHealth>[] = [
  { key: "endpoint", header: "Endpoint", primary: true, cell: (a) => <span className="whitespace-nowrap font-medium text-ink">{a.endpoint}</span> },
  { key: "status", header: "Status", cell: (a) => <StatusBadge tone={apiStatusTone[a.status]}>{a.status}</StatusBadge> },
  { key: "checked", header: "Last Checked", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.lastChecked === "—" ? "—" : formatRelativeTime(a.lastChecked)}</span> },
  { key: "latency", header: "Latency", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.latency}</span> },
  { key: "error", header: "Error Rate", align: "right", cell: (a) => <span className={cn("font-mono text-xs tnum", a.errorRate > 1 ? "text-warning" : "text-ink-muted")}>{a.errorRate.toFixed(1)}%</span> },
  { key: "uptime", header: "Uptime", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.uptime ? `${a.uptime}%` : "—"}</span> },
  { key: "lastError", header: "Last Error", cell: (a) => <span className="text-xs text-ink-faint">{a.lastError}</span> },
];

function ApiHealthTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(apiHealth, filters);
  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="API & webhook health" subtitle="Internal endpoints & webhooks · safe summaries only" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={apiCols} rows={rows} rowKey={(a) => a.endpoint} empty={filteredEmpty} onRowLabel={(a) => <StatusBadge tone={apiStatusTone[a.status]}>{a.status}</StatusBadge>} />
        </div>
        {globalHint}
      </Panel>
      <ChartCard title="API latency over time" subtitle="Milliseconds">
        <AreaTrend data={apiLatencyOverTime} series={[{ key: "value", name: "Latency (ms)", color: CHART.sky }]} height={180} />
      </ChartCard>
    </div>
  );
}

/* --------------------------------- Job queue -------------------------------- */

const jobCols: Column<JobRow>[] = [
  { key: "name", header: "Job", primary: true, cell: (j) => <span className="whitespace-nowrap font-mono text-xs font-semibold text-ink">{j.name}</span> },
  { key: "agent", header: "Agent", cell: (j) => <span className="whitespace-nowrap text-xs text-ink-muted">{j.agent}</span> },
  { key: "status", header: "Status", cell: (j) => <StatusBadge tone={jobStatusTone[j.status]}>{j.status}</StatusBadge> },
  { key: "queued", header: "Queued At", cell: (j) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(j.queuedAt)}</span> },
  { key: "attempts", header: "Attempts", align: "right", cell: (j) => <span className="font-mono text-sm text-ink tnum">{j.attempts}</span> },
  { key: "retry", header: "Next Retry", cell: (j) => <span className="whitespace-nowrap text-xs text-ink-muted">{j.nextRetry === "—" ? "—" : formatRelativeTime(j.nextRetry)}</span> },
  { key: "error", header: "Error", cell: (j) => <span className="text-xs text-ink-faint">{j.error}</span> },
  { key: "actions", header: "", align: "right", cell: (j) => (j.status === "Failed" || j.status === "Retrying" ? <Button size="sm" variant="secondary"><RotateCw className="h-3.5 w-3.5" /> Retry</Button> : <Button size="sm" variant="ghost">View</Button>) },
];

function JobQueueTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(jobQueue, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Job queue" subtitle="Background & scheduled jobs · Celery / Redis view" className="p-4" action={<StatusBadge tone="danger">{rows.filter((j) => j.status === "Failed").length} failed</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={jobCols} rows={rows} rowKey={(j) => j.name} empty={filteredEmpty} onRowLabel={(j) => <StatusBadge tone={jobStatusTone[j.status]}>{j.status}</StatusBadge>} />
      </div>
      {globalHint}
    </Panel>
  );
}

/* ------------------------------- LLM / cost usage --------------------------- */

const llmCols: Column<LlmUsageRow>[] = [
  { key: "agent", header: "Agent", primary: true, cell: (l) => <span className="whitespace-nowrap font-medium text-ink">{l.agent}</span> },
  { key: "calls", header: "Calls", align: "right", cell: (l) => <span className="font-mono text-sm text-ink tnum">{l.calls.toLocaleString()}</span> },
  { key: "tokens", header: "Tokens", align: "right", cell: (l) => <span className="font-mono text-xs text-ink-muted tnum">{(l.tokens / 1000).toFixed(0)}k</span> },
  { key: "cost", header: "Est. Cost", align: "right", cell: (l) => <span className="font-mono text-sm text-ink tnum">{formatCurrency(l.estCost)}</span> },
  { key: "mode", header: "Mode", cell: (l) => <StatusBadge tone={l.mode === "live" ? "success" : "info"} dot={false}>{l.mode}</StatusBadge> },
];

function LlmUsageTab() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="LLM cost & usage" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MiniMetric label="Calls today" value="1,284" delta={12} tone="plum" />
        <MiniMetric label="Est. cost" value="AED 3.2K" delta={26} tone="plum" />
        <MiniMetric label="Tokens used" value="1.9M" tone="info" />
        <MiniMetric label="Mode" value="Staging" tone="info" />
      </div>
      <Panel padded={false}>
        <PanelHeader title="LLM usage by agent" subtitle="Calls, tokens & estimated cost" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={llmCols} rows={llmUsage} rowKey={(l) => l.agent} />
        </div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="LLM calls by agent" subtitle="Today">
          <BarSeries data={llmCallsByAgent} horizontal colorByIndex height={220} />
        </ChartCard>
        <ChartCard title="Estimated cost by agent" subtitle="AED · today">
          <BarSeries data={costByAgent} horizontal currency color={CHART.plum} height={220} />
        </ChartCard>
      </div>
      <p className="flex items-center gap-1.5 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Costs are estimates — no provider keys or tokens are stored or shown.</p>
    </div>
  );
}

/* -------------------------------- Deployments ------------------------------- */

const deployCols: Column<DeployRow>[] = [
  { key: "app", header: "App", primary: true, cell: (d) => <span className="whitespace-nowrap font-medium text-ink">{d.app}</span> },
  { key: "env", header: "Environment", cell: (d) => <StatusBadge tone={d.environment === "Production" ? "rose" : d.environment === "Staging" ? "info" : "neutral"} dot={false}>{d.environment}</StatusBadge> },
  { key: "version", header: "Version", cell: (d) => <span className="font-mono text-xs text-ink-muted tnum">{d.version}</span> },
  { key: "last", header: "Last Deploy", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{d.lastDeploy === "—" ? "—" : formatRelativeTime(d.lastDeploy)}</span> },
  { key: "deploy", header: "Deploy Status", cell: (d) => <StatusBadge tone={deployStatusTone[d.deployStatus]}>{d.deployStatus}</StatusBadge> },
  { key: "build", header: "Build", cell: (d) => <StatusBadge tone={buildStatusTone[d.buildStatus]} dot={false}>{d.buildStatus}</StatusBadge> },
  { key: "owner", header: "Owner", cell: (d) => <span className="text-xs text-ink-muted">{d.owner}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">View</Button> },
];

function DeploymentsTab() {
  const { filters } = useFilters();
  // Deployments are global/technical (no geo) — they pass through geo filters and
  // stay visible; the note below states this explicitly.
  const rows = applyGlobalFilters(deployments, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Deployments" subtitle="App versions & environments" className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={deployCols} rows={rows} rowKey={(d) => `${d.app}-${d.environment}`} empty={filteredEmpty} onRowLabel={(d) => <StatusBadge tone={deployStatusTone[d.deployStatus]}>{d.deployStatus}</StatusBadge>} />
      </div>
      {globalHint}
    </Panel>
  );
}

/* ------------------------------ Integration status -------------------------- */

function IntegrationsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(integrations, filters);
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="Integration status" subtitle="Connection status across integrations" action={<Plug className="h-4 w-4 text-rose" />} />
        {rows.length === 0 ? (
          filteredEmpty
        ) : (
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((i) => (
              <ConnectedAppRow key={i.name} app={{ name: i.name, category: i.category, status: i.status === "Standby" ? "Coming soon" : i.status }} />
            ))}
          </div>
        )}
        {globalHint}
      </Panel>
      <ChartCard title="Integration status breakdown" subtitle="18 integrations">
        <DonutChart data={integrationBreakdown} colors={[CHART.sky, CHART.amber, "rgb(var(--ink-faint))"]} centerValue="18" centerLabel="Total" height={220} />
      </ChartCard>
    </div>
  );
}

/* -------------------------------- Logs & audit ------------------------------ */

const logCols: Column<LogRow>[] = [
  { key: "time", header: "Timestamp", primary: true, cell: (l) => <span className="whitespace-nowrap font-mono text-xs text-ink-muted tnum">{new Date(l.timestamp).toLocaleTimeString("en-GB")}</span> },
  { key: "module", header: "Module", cell: (l) => <span className="whitespace-nowrap text-xs text-ink-muted">{l.module}</span> },
  { key: "event", header: "Event", cell: (l) => <span className="whitespace-nowrap font-mono text-xs text-ink">{l.event}</span> },
  { key: "source", header: "Source", cell: (l) => <span className="whitespace-nowrap text-xs text-ink-muted">{l.source}</span> },
  { key: "severity", header: "Severity", cell: (l) => <StatusBadge tone={logSeverityTone[l.severity]} dot={false}>{l.severity}</StatusBadge> },
  { key: "message", header: "Message", cell: (l) => <span className="text-xs text-ink-faint">{l.message}</span> },
  { key: "trace", header: "Trace ID", cell: (l) => <span className="font-mono text-xxs text-ink-faint">{l.traceId}</span> },
];

function LogsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(logs, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Logs & audit" subtitle="System events — safe summaries, no secrets or raw payloads" className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={logCols} rows={rows} rowKey={(l) => l.traceId} empty={filteredEmpty} onRowLabel={(l) => <StatusBadge tone={logSeverityTone[l.severity]} dot={false}>{l.severity}</StatusBadge>} />
      </div>
      {globalHint}
      <p className="flex items-center gap-1.5 border-t border-border px-4 py-3 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Logs are safe summaries only — no API keys, tokens, secrets or raw environment values are shown.</p>
    </Panel>
  );
}

/* --------------------------------- Overview --------------------------------- */

function SafetyBanner() {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
      <div>
        <p className="text-xs font-semibold text-ink">No secrets stored</p>
        <p className="text-xxs text-ink-muted">No API keys, tokens or raw environment values are shown. Errors are safe summaries.</p>
      </div>
    </div>
  );
}

function OverviewSection() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="Automation overview" />
      <StatGrid stats={devKpis} cols="auto" />
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Live vs staged agents" subtitle="Status split">
          <DonutChart data={liveVsMock} colors={[CHART.teal, CHART.sky, "rgb(var(--ink-faint))", CHART.amber, CHART.rose]} centerValue="22" centerLabel="Agents" height={200} />
        </ChartCard>
        <ChartCard title="LLM calls by agent" subtitle="Today" className="lg:col-span-2">
          <BarSeries data={llmCallsByAgent} horizontal colorByIndex height={200} />
        </ChartCard>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2"><AutomationOverviewTab /></div>
        <aside className="space-y-4">
          <SafetyBanner />
          <Panel>
            <PanelHeader title="System activity" subtitle="Latest technical events" />
            <ActivityTimeline events={devActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Agent actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "View Logs", icon: Eye },
                { label: "Retry Job", icon: RotateCw },
                { label: "Pause Agent", icon: Pause },
                { label: "Resume Agent", icon: Play },
                { label: "View Config", icon: Settings2 },
                { label: "Assign Owner", icon: UserPlus },
                { label: "Create Issue", icon: CirclePlus },
                { label: "Health Check", icon: Activity },
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

/* --------------------------------- Router ----------------------------------- */

/** Renders one Dev & Automation subsection by slug (see lib/dashboard/sections.ts). */
export function DevSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "overview": return <OverviewSection />;
    case "agent-health": return <AgentHealthTab />;
    case "technical-issues": return <TechIssuesTab />;
    case "api-webhook-health": return <ApiHealthTab />;
    case "job-queue": return <JobQueueTab />;
    case "llm-cost-usage": return <LlmUsageTab />;
    case "deployments": return <DeploymentsTab />;
    case "integration-status": return <IntegrationsTab />;
    case "logs-audit": return <LogsTab />;
    default: return <OverviewSection />;
  }
}
