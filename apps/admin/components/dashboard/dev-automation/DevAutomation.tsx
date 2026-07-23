"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Bot, Boxes, Plug, ScrollText, Server, AlertTriangle, Gauge, Rocket, ShieldCheck } from "lucide-react";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, DataPreviewTable,
  EmptyState, StatusBadge, SnapshotBadge,
  type MinimalKpi, type WorkflowTab, type PreviewColumn,
} from "@/components/dashboard/minimal";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import {
  agentHealth,
  agentStatusToneD,
  agentSlug,
  agentNeedsAttention,
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
  integrations,
  integrationStatusTone,
  logs,
  logSeverityTone,
  type AgentHealth,
  type TechIssue,
  type ApiHealth,
  type JobRow,
  type LlmUsageRow,
  type DeployRow,
  type IntegrationRow,
  type LogRow,
} from "@/lib/dashboard/dev-automation-data";

/* ============================================================================
 * Dev & Automation — minimal, progressive-disclosure surfaces.
 *
 * Main pages stay light: a curated KPI strip, optional workflow/status tabs, and
 * a single-column list (or a calm preview table for metric/log-heavy views). No
 * record actions live here — the primary records (agents, jobs) click through to
 * a full detail page where all actions live behind an ActionMenu. Non-primary
 * views are consistent read-only previews. Global filters are preserved via
 * applyGlobalFilters; the SubsectionShell renders the header + FilterBar.
 * ========================================================================== */

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

/** A small right-aligned row that mirrors global-filter awareness. */
function FilterAwareRow({ tabs, value, onChange, active }: {
  tabs?: WorkflowTab[];
  value?: string;
  onChange?: (id: string) => void;
  active: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {tabs && value && onChange ? <WorkflowTabs tabs={tabs} value={value} onChange={onChange} /> : <span />}
      <SnapshotBadge active={active} />
    </div>
  );
}

/* ------------------------------- Agent health ------------------------------- */

type AgentTabId = "all" | "live" | "staged" | "attention";

const AGENT_TABS: { id: AgentTabId; label: string; test: (a: AgentHealth) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "live", label: "Live", test: (a) => a.status === "Live" },
  { id: "staged", label: "Staged", test: (a) => a.status === "Staged" || a.status === "Scheduled" },
  { id: "attention", label: "Needs attention", test: agentNeedsAttention },
];

function AgentHealthTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<AgentTabId>("all");
  const base = useMemo(() => applyGlobalFilters(agentHealth, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Total agents", value: String(base.length) },
    { label: "Live", value: String(base.filter((a) => a.status === "Live").length), tone: "success" },
    { label: "Staged", value: String(base.filter((a) => a.status === "Staged" || a.status === "Scheduled").length) },
    { label: "Needs attention", value: String(base.filter(agentNeedsAttention).length), tone: "warning" },
  ];

  const tabs: WorkflowTab[] = AGENT_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter(t.test).length }));
  const rows = base.filter(AGENT_TABS.find((t) => t.id === tab)!.test);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow tabs={tabs} value={tab} onChange={(id) => setTab(id as AgentTabId)} active={isFiltered} />

      {rows.length === 0 ? (
        <EmptyState icon={Bot} title="No agents in this view" description="No agents match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((a) => (
            <CompactRecordCard
              key={a.name}
              title={a.name}
              status={{ label: a.status, tone: agentStatusToneD[a.status] }}
              fields={[
                { label: "Category", value: a.category },
                { label: "Success", value: a.successRate ? `${a.successRate}%` : "—" },
                { label: "Last run", value: fmtTime(a.lastRun) },
              ]}
              meta={
                a.issues > 0
                  ? <StatusBadge tone="danger" dot={false}>{a.issues} issue{a.issues === 1 ? "" : "s"}</StatusBadge>
                  : <span className="text-xxs text-ink-faint">{a.mode}</span>
              }
              href={`/dev-automation/agent-health/${agentSlug(a.name)}?tab=${tab}`}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* --------------------------------- Job queue -------------------------------- */

type JobTabId = "all" | "queued" | "running" | "retrying" | "failed" | "done";

const JOB_TABS: { id: JobTabId; label: string; test: (j: JobRow) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "queued", label: "Queued", test: (j) => j.status === "Queued" },
  { id: "running", label: "Running", test: (j) => j.status === "Running" },
  { id: "retrying", label: "Retrying", test: (j) => j.status === "Retrying" },
  { id: "failed", label: "Failed", test: (j) => j.status === "Failed" },
  { id: "done", label: "Done", test: (j) => j.status === "Done" },
];

function JobQueueTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<JobTabId>("all");
  const base = useMemo(() => applyGlobalFilters(jobQueue, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Queued", value: String(base.filter((j) => j.status === "Queued").length) },
    { label: "Running", value: String(base.filter((j) => j.status === "Running").length), tone: "rose" },
    { label: "Retrying", value: String(base.filter((j) => j.status === "Retrying").length), tone: "warning" },
    { label: "Failed", value: String(base.filter((j) => j.status === "Failed").length), tone: "danger" },
  ];

  const tabs: WorkflowTab[] = JOB_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter(t.test).length }));
  const rows = base.filter(JOB_TABS.find((t) => t.id === tab)!.test);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow tabs={tabs} value={tab} onChange={(id) => setTab(id as JobTabId)} active={isFiltered} />

      {rows.length === 0 ? (
        <EmptyState icon={Boxes} title="No jobs in this view" description="No background jobs match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((j) => (
            <CompactRecordCard
              key={j.name}
              title={<span className="font-mono">{j.name}</span>}
              status={{ label: j.status, tone: jobStatusTone[j.status] }}
              fields={[
                { label: "Agent", value: j.agent },
                { label: "Attempts", value: j.attempts },
                { label: "Queued", value: fmtTime(j.queuedAt) },
              ]}
              meta={
                j.nextRetry !== "—"
                  ? <span className="text-xxs text-ink-faint">Retry {fmtTime(j.nextRetry)}</span>
                  : j.error !== "—"
                    ? <span className="text-xxs text-danger">{j.error}</span>
                    : null
              }
              href={`/dev-automation/job-queue/${encodeURIComponent(j.name)}?tab=${tab}`}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ------------------------------ Technical issues ---------------------------- */

type IssueTabId = "all" | "open" | "in-progress" | "blocked" | "resolved";

const ISSUE_TABS: { id: IssueTabId; label: string; test: (i: TechIssue) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "open", label: "Open", test: (i) => i.status === "Open" },
  { id: "in-progress", label: "In progress", test: (i) => i.status === "In Progress" },
  { id: "blocked", label: "Blocked", test: (i) => i.status === "Blocked" },
  { id: "resolved", label: "Resolved", test: (i) => i.status === "Resolved" },
];

function TechIssuesTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<IssueTabId>("all");
  const base = useMemo(() => applyGlobalFilters(techIssues, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Open", value: String(base.filter((i) => i.status === "Open").length), tone: "warning" },
    { label: "In progress", value: String(base.filter((i) => i.status === "In Progress").length) },
    { label: "Blocked", value: String(base.filter((i) => i.status === "Blocked").length), tone: "danger" },
    { label: "High severity", value: String(base.filter((i) => i.severity === "High" || i.severity === "Critical").length), tone: "danger" },
  ];

  const tabs: WorkflowTab[] = ISSUE_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter(t.test).length }));
  const rows = base.filter(ISSUE_TABS.find((t) => t.id === tab)!.test);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow tabs={tabs} value={tab} onChange={(id) => setTab(id as IssueTabId)} active={isFiltered} />

      {rows.length === 0 ? (
        <EmptyState icon={AlertTriangle} title="No issues in this view" description="No technical issues match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((i) => (
            <CompactRecordCard
              key={i.id}
              id={i.id}
              title={i.title}
              status={{ label: i.severity, tone: severityTone[i.severity] }}
              fields={[
                { label: "Module", value: i.module },
                { label: "Owner", value: i.owner },
                { label: "Updated", value: fmtTime(i.lastUpdate) },
              ]}
              meta={<StatusBadge tone={issueStatusTone[i.status]} dot={false}>{i.status}</StatusBadge>}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ---------------------------- API & webhook health -------------------------- */

const apiColumns: PreviewColumn<ApiHealth>[] = [
  { key: "endpoint", header: "Endpoint", primary: true, cell: (a) => <span className="font-medium text-ink">{a.endpoint}</span> },
  { key: "status", header: "Status", cell: (a) => <StatusBadge tone={apiStatusTone[a.status]} dot={false}>{a.status}</StatusBadge> },
  { key: "latency", header: "Latency", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.latency}</span> },
  { key: "error", header: "Error rate", align: "right", cell: (a) => <span className={`font-mono text-xs tnum ${a.errorRate > 1 ? "text-warning" : "text-ink-muted"}`}>{a.errorRate.toFixed(1)}%</span> },
  { key: "uptime", header: "Uptime", align: "right", cell: (a) => <span className="font-mono text-xs text-ink-muted tnum">{a.uptime ? `${a.uptime}%` : "—"}</span> },
];

function ApiHealthTab() {
  const { filters } = useFilters();
  const base = useMemo(() => applyGlobalFilters(apiHealth, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Operational", value: String(base.filter((a) => a.status === "Operational").length), tone: "success" },
    { label: "Degraded", value: String(base.filter((a) => a.status === "Degraded").length), tone: "warning" },
    { label: "Standby", value: String(base.filter((a) => a.status === "Standby").length) },
    { label: "Endpoints", value: String(base.length) },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow active={isFiltered} />
      <DataPreviewTable
        columns={apiColumns}
        rows={base}
        rowKey={(a) => a.endpoint}
        empty={<EmptyState icon={Server} title="No endpoints" description="No endpoints match the active filters." />}
      />
    </div>
  );
}

/* ------------------------------- LLM / cost usage --------------------------- */

const llmColumns: PreviewColumn<LlmUsageRow>[] = [
  { key: "agent", header: "Agent", primary: true, cell: (l) => <span className="font-medium text-ink">{l.agent}</span> },
  { key: "calls", header: "Calls", align: "right", cell: (l) => <span className="font-mono text-sm text-ink tnum">{l.calls.toLocaleString()}</span> },
  { key: "tokens", header: "Tokens", align: "right", cell: (l) => <span className="font-mono text-xs text-ink-muted tnum">{(l.tokens / 1000).toFixed(0)}k</span> },
  { key: "cost", header: "Est. cost", align: "right", cell: (l) => <span className="font-mono text-sm text-ink tnum">{formatCurrency(l.estCost)}</span> },
  { key: "mode", header: "Mode", cell: (l) => <StatusBadge tone={l.mode === "live" ? "success" : "info"} dot={false}>{l.mode}</StatusBadge> },
];

function LlmUsageTab() {
  const { filters } = useFilters();
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Calls today", value: "1,284" },
    { label: "Est. cost", value: "AED 3.2K", tone: "plum" },
    { label: "Tokens used", value: "1.9M" },
    { label: "Mode", value: "Staging" },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow active={isFiltered} />
      <DataPreviewTable columns={llmColumns} rows={llmUsage} rowKey={(l) => l.agent} />
      <PrivacyNote text="Costs are estimates — no provider keys or tokens are stored or shown." />
    </div>
  );
}

/* -------------------------------- Deployments ------------------------------- */

function DeploymentsTab() {
  const { filters } = useFilters();
  const base = useMemo(() => applyGlobalFilters(deployments, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Deployed", value: String(base.filter((d) => d.deployStatus === "Success").length), tone: "success" },
    { label: "Building", value: String(base.filter((d) => d.deployStatus === "Building").length) },
    { label: "Not deployed", value: String(base.filter((d) => d.deployStatus === "Not deployed").length) },
    { label: "Builds passing", value: String(base.filter((d) => d.buildStatus === "Passing").length), tone: "success" },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow active={isFiltered} />
      {base.length === 0 ? (
        <EmptyState icon={Rocket} title="No deployments" description="No deployments match the active filters." />
      ) : (
        <RecordList>
          {base.map((d: DeployRow) => (
            <CompactRecordCard
              key={`${d.app}-${d.environment}`}
              title={d.app}
              status={{ label: d.deployStatus, tone: deployStatusTone[d.deployStatus] }}
              fields={[
                { label: "Environment", value: d.environment },
                { label: "Version", value: <span className="font-mono">{d.version}</span> },
                { label: "Last deploy", value: fmtTime(d.lastDeploy) },
              ]}
              meta={<span className="text-xxs text-ink-faint">Build: {d.buildStatus}</span>}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ------------------------------ Integration status -------------------------- */

type IntegrationTabId = "all" | "standby" | "not-connected";

const INTEGRATION_TABS: { id: IntegrationTabId; label: string; test: (i: IntegrationRow) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "standby", label: "Standby", test: (i) => i.status === "Standby" },
  { id: "not-connected", label: "Not connected", test: (i) => i.status === "Not connected" },
];

function IntegrationsTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<IntegrationTabId>("all");
  const base = useMemo(() => applyGlobalFilters(integrations, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Connected", value: String(base.filter((i) => i.status === "Connected").length), tone: "success" },
    { label: "Standby", value: String(base.filter((i) => i.status === "Standby").length), tone: "warning" },
    { label: "Not connected", value: String(base.filter((i) => i.status === "Not connected").length) },
    { label: "Total", value: String(base.length) },
  ];

  const tabs: WorkflowTab[] = INTEGRATION_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter(t.test).length }));
  const rows = base.filter(INTEGRATION_TABS.find((t) => t.id === tab)!.test);

  const label = (s: IntegrationRow["status"]) => (s === "Standby" ? "Coming soon" : s);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow tabs={tabs} value={tab} onChange={(id) => setTab(id as IntegrationTabId)} active={isFiltered} />

      {rows.length === 0 ? (
        <EmptyState icon={Plug} title="No integrations in this view" description="No integrations match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((i) => (
            <CompactRecordCard
              key={i.name}
              title={i.name}
              status={{ label: label(i.status), tone: integrationStatusTone[i.status] }}
              fields={[{ label: "Category", value: i.category }]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* -------------------------------- Logs & audit ------------------------------ */

type LogTabId = "all" | "info" | "warning" | "error" | "debug";

const LOG_TABS: { id: LogTabId; label: string; test: (l: LogRow) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "info", label: "Info", test: (l) => l.severity === "Info" },
  { id: "warning", label: "Warning", test: (l) => l.severity === "Warning" },
  { id: "error", label: "Error", test: (l) => l.severity === "Error" },
  { id: "debug", label: "Debug", test: (l) => l.severity === "Debug" },
];

const logColumns: PreviewColumn<LogRow>[] = [
  { key: "time", header: "Time", primary: true, cell: (l) => <span className="font-mono text-xs text-ink-muted tnum">{new Date(l.timestamp).toLocaleTimeString("en-GB")}</span> },
  { key: "module", header: "Module", cell: (l) => <span className="text-xs text-ink-muted">{l.module}</span> },
  { key: "event", header: "Event", cell: (l) => <span className="font-mono text-xs text-ink">{l.event}</span> },
  { key: "severity", header: "Severity", cell: (l) => <StatusBadge tone={logSeverityTone[l.severity]} dot={false}>{l.severity}</StatusBadge> },
  { key: "message", header: "Message", cell: (l) => <span className="text-xs text-ink-faint">{l.message}</span> },
];

function LogsTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<LogTabId>("all");
  const base = useMemo(() => applyGlobalFilters(logs, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Info", value: String(base.filter((l) => l.severity === "Info").length) },
    { label: "Warning", value: String(base.filter((l) => l.severity === "Warning").length), tone: "warning" },
    { label: "Error", value: String(base.filter((l) => l.severity === "Error").length), tone: "danger" },
    { label: "Debug", value: String(base.filter((l) => l.severity === "Debug").length) },
  ];

  const tabs: WorkflowTab[] = LOG_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter(t.test).length }));
  const rows = base.filter(LOG_TABS.find((t) => t.id === tab)!.test);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow tabs={tabs} value={tab} onChange={(id) => setTab(id as LogTabId)} active={isFiltered} />
      <DataPreviewTable
        columns={logColumns}
        rows={rows}
        rowKey={(l) => l.traceId}
        empty={<EmptyState icon={ScrollText} title="No log events" description="No events match this severity and the active filters." />}
      />
      <PrivacyNote text="Logs are safe summaries only — no API keys, tokens, secrets or raw environment values are shown." />
    </div>
  );
}

/* --------------------------------- Overview --------------------------------- */

function SectionLabel({ children }: { children: ReactNode }) {
  return <h2 className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{children}</h2>;
}

function PrivacyNote({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
      <ShieldCheck className="h-3 w-3 shrink-0" /> {text}
    </p>
  );
}

const overviewLogColumns: PreviewColumn<LogRow>[] = [
  { key: "time", header: "Time", primary: true, cell: (l) => <span className="font-mono text-xs text-ink-muted tnum">{new Date(l.timestamp).toLocaleTimeString("en-GB")}</span> },
  { key: "module", header: "Module", cell: (l) => <span className="text-xs text-ink-muted">{l.module}</span> },
  { key: "event", header: "Event", cell: (l) => <span className="font-mono text-xs text-ink">{l.event}</span> },
  { key: "severity", header: "Severity", cell: (l) => <StatusBadge tone={logSeverityTone[l.severity]} dot={false}>{l.severity}</StatusBadge> },
];

function OverviewSection() {
  const { filters } = useFilters();
  const agents = useMemo(() => applyGlobalFilters(agentHealth, filters), [filters]);
  const jobs = useMemo(() => applyGlobalFilters(jobQueue, filters), [filters]);
  const issues = useMemo(() => applyGlobalFilters(techIssues, filters), [filters]);
  const recentLogs = useMemo(() => applyGlobalFilters(logs, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const attention = agents.filter(agentNeedsAttention);

  const kpis: MinimalKpi[] = [
    { label: "Total agents", value: String(agents.length) },
    { label: "Live agents", value: String(agents.filter((a) => a.status === "Live").length), tone: "success" },
    { label: "Failed jobs", value: String(jobs.filter((j) => j.status === "Failed").length), tone: "danger" },
    { label: "Open issues", value: String(issues.filter((i) => i.status !== "Resolved").length), tone: "warning" },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterAwareRow active={isFiltered} />

      <div className="space-y-3">
        <SectionLabel>Needs attention</SectionLabel>
        {attention.length === 0 ? (
          <EmptyState icon={Gauge} title="All agents healthy" description="No agents currently need attention." />
        ) : (
          <RecordList>
            {attention.map((a) => (
              <CompactRecordCard
                key={a.name}
                title={a.name}
                status={{ label: a.status, tone: agentStatusToneD[a.status] }}
                fields={[
                  { label: "Category", value: a.category },
                  { label: "Success", value: a.successRate ? `${a.successRate}%` : "—" },
                  { label: "Last run", value: fmtTime(a.lastRun) },
                ]}
                meta={a.issues > 0 ? <StatusBadge tone="danger" dot={false}>{a.issues} issue{a.issues === 1 ? "" : "s"}</StatusBadge> : undefined}
                href={`/dev-automation/agent-health/${agentSlug(a.name)}`}
              />
            ))}
          </RecordList>
        )}
      </div>

      <div className="space-y-3">
        <SectionLabel>Recent activity</SectionLabel>
        <DataPreviewTable
          columns={overviewLogColumns}
          rows={recentLogs}
          rowKey={(l) => l.traceId}
          empty={<EmptyState icon={ScrollText} title="No recent activity" description="No system events match the active filters." />}
        />
      </div>

      <PrivacyNote text="No secrets stored — no API keys, tokens or raw environment values are shown. Errors are safe summaries." />
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
