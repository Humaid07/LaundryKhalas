"use client";

import { useEffect, useState } from "react";
import {
  Sparkles, Bot, SearchX, FileText, TrendingUp, TrendingDown, Minus, MapPin,
} from "lucide-react";
import { seoAgentApi, type SeoAgentHealthDTO } from "@/lib/dashboard/seo-agent-api";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { SeoAgent, AgentStatus, KpiStat } from "@/lib/dashboard/types";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { agentStatusTone, priorityTone } from "@/lib/dashboard/status-maps";
import {
  seoAgents, seoKpis, seoTasks, seoBrief,
} from "@/lib/dashboard/mock-data";
import {
  gscPages, indexingQueue, indexStateTone, hyperlocalPages, hyperlocalStatusTone,
  techSeoIssues, techSeoSeverityTone, competitors, aiSearch, aiPresenceTone, slugifyAgent,
  type GscPage, type IndexRow, type HyperlocalPage, type TechSeoIssue,
  type Competitor, type AiSearchRow,
} from "@/lib/dashboard/seo-data";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, DataPreviewTable,
  StatusBadge, EmptyState, SnapshotBadge, type MinimalKpi, type WorkflowTab, type PreviewColumn,
} from "@/components/dashboard/minimal";
import type { Tone } from "@/lib/dashboard/types";
import { cn } from "@/lib/utils";

/* --------------------------- live data hook (API) --------------------------- */

/** Fetch a subsection's rows from the SEO backend; fall back to the static list
 *  until it resolves (or if unreachable). The fetcher must be module-stable. */
function useSeoLive<T>(fetcher: () => Promise<T[]>, fallback: T[]): T[] {
  const [rows, setRows] = useState<T[]>(fallback);
  useEffect(() => {
    let active = true;
    fetcher()
      .then((r) => {
        if (active && Array.isArray(r) && r.length) setRows(r);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [fetcher]);
  return rows;
}

/* --------------------------------- shared ----------------------------------- */

const noMatch = (
  <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />
);

/** Curate a KpiStat[] into 3–4 minimal KPIs (label + value + optional tone). */
function toMinimalKpis(stats: KpiStat[], take = 4): MinimalKpi[] {
  return stats.slice(0, take).map((s) => ({ label: s.label, value: String(s.value), tone: s.tone }));
}

function useSnapshot() {
  const { filters } = useFilters();
  return { filters, isFiltered: activeFilterCount(filters) > 0 };
}

/** A tabs row with a right-aligned snapshot badge (site-wide views). */
function TabsRow({
  tabs, value, onChange, isFiltered,
}: {
  tabs: WorkflowTab[]; value: string; onChange: (id: string) => void; isFiltered: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <WorkflowTabs tabs={tabs} value={value} onChange={onChange} />
      <SnapshotBadge active={isFiltered} label="Global / site-wide" />
    </div>
  );
}

/* -------------------------------- Overview ---------------------------------- */

function BriefCard() {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface p-5 shadow-card">
      <div className="flex items-center gap-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose/12 text-rose"><Sparkles className="h-4 w-4" /></span>
        <div className="min-w-0">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Daily SEO brief · {seoBrief.date}</p>
          <h3 className="truncate font-display text-[0.95rem] font-semibold text-ink">{seoBrief.headline}</h3>
        </div>
      </div>
      <ul className="mt-4 space-y-2.5">
        {seoBrief.items.slice(0, 3).map((it) => (
          <li key={it.title} className="flex gap-2.5">
            <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", toneBg[it.tone])} />
            <p className="text-xs text-ink-muted"><span className="font-medium text-ink">{it.title}:</span> {it.text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

const toneBg: Record<Tone, string> = {
  rose: "bg-rose", success: "bg-success", warning: "bg-warning", danger: "bg-danger",
  info: "bg-info", neutral: "bg-ink-faint", plum: "bg-plum",
};

const needsAttention = (a: SeoAgent) =>
  a.approvalRequired || a.status === "Needs Review" || a.status === "Awaiting Approval";

function OverviewSection() {
  const kpis = toMinimalKpis(useSeoLive(seoAgentApi.getOverviewKpis, seoKpis));
  const attention = seoAgents.filter(needsAttention);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <BriefCard />
      <div className="space-y-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Agents needing attention</p>
        {attention.length === 0 ? (
          <EmptyState icon={Bot} title="Nothing needs review" description="All agents are running cleanly." />
        ) : (
          <RecordList>
            {attention.map((a) => (
              <CompactRecordCard
                key={a.name}
                title={a.name}
                status={{ label: a.status, tone: agentStatusTone[a.status] }}
                fields={[
                  { label: "Category", value: a.category },
                  { label: "Open issues", value: String(a.openIssues) },
                  { label: "Last run", value: fmt(a.lastRun) },
                ]}
                href={`/seo-agents/agents/${slugifyAgent(a.name)}`}
              />
            ))}
          </RecordList>
        )}
      </div>
    </div>
  );
}

/* ------------------------------- Agent fleet -------------------------------- */

const SECTION_CATEGORY: Record<string, SeoAgent["category"]> = {
  "technical-seo": "Technical", indexing: "Technical", "gsc-performance": "Technical",
  "content-pipeline": "Content", "hyperlocal-pages": "Content",
  competitors: "Intelligence", "ai-search": "Intelligence", reports: "Intelligence",
};

function healthStatusToCard(h: SeoAgentHealthDTO): AgentStatus {
  if (h.human_approval_required && h.approval_tasks > 0) return "Awaiting Approval";
  if (h.status === "Live") return "Active";
  if (h.status === "Paused") return "Paused";
  return "Scheduled";
}

function toCardAgent(h: SeoAgentHealthDTO): SeoAgent {
  return {
    name: h.name,
    status: healthStatusToCard(h),
    lastRun: h.last_run ? h.last_run : "—",
    nextRun: h.next_run,
    outputs: h.findings,
    openIssues: h.issues,
    approvalRequired: h.human_approval_required,
    category: SECTION_CATEGORY[h.dashboard_sections[0]] ?? "Intelligence",
  };
}

const fmt = (iso: string) => (iso === "—" || !iso ? "—" : formatRelativeTime(iso));

type FleetTab = "all" | "active" | "attention" | "scheduled" | "paused";
const FLEET_FILTERS: Record<FleetTab, (a: SeoAgent) => boolean> = {
  all: () => true,
  active: (a) => a.status === "Active",
  attention: needsAttention,
  scheduled: (a) => a.status === "Scheduled",
  paused: (a) => a.status === "Paused",
};
const FLEET_LABELS: { id: FleetTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "attention", label: "Needs attention" },
  { id: "scheduled", label: "Scheduled" },
  { id: "paused", label: "Paused" },
];

function AgentFleetSection() {
  const [agents, setAgents] = useState<SeoAgent[]>(seoAgents);
  const [tab, setTab] = useState<FleetTab>("all");
  useEffect(() => {
    let active = true;
    seoAgentApi.listSeoAgentHealth()
      .then((rows) => { if (active && rows.length) setAgents(rows.map(toCardAgent)); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  const kpis: MinimalKpi[] = [
    { label: "Total agents", value: String(agents.length) },
    { label: "Active", value: String(agents.filter(FLEET_FILTERS.active).length), tone: "success" },
    { label: "Needs attention", value: String(agents.filter(FLEET_FILTERS.attention).length), tone: "warning" },
    { label: "Paused", value: String(agents.filter(FLEET_FILTERS.paused).length) },
  ];
  const tabs: WorkflowTab[] = FLEET_LABELS.map((t) => ({ id: t.id, label: t.label, count: agents.filter(FLEET_FILTERS[t.id]).length }));
  const rows = agents.filter(FLEET_FILTERS[tab]);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as FleetTab)} />
      {rows.length === 0 ? (
        <EmptyState icon={Bot} title="No agents in this view" description="No agents match this status." />
      ) : (
        <RecordList>
          {rows.map((a) => (
            <CompactRecordCard
              key={a.name}
              title={a.name}
              status={{ label: a.status, tone: agentStatusTone[a.status] }}
              fields={[
                { label: "Category", value: a.category },
                { label: "Last run", value: fmt(a.lastRun) },
                { label: "Outputs", value: String(a.outputs) },
              ]}
              meta={a.openIssues > 0 ? <StatusBadge tone="warning" dot={false}>{a.openIssues} issue{a.openIssues === 1 ? "" : "s"}</StatusBadge> : undefined}
              href={`/seo-agents/agents/${slugifyAgent(a.name)}`}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ----------------------------- GSC performance ------------------------------ */

const gscCols: PreviewColumn<GscPage>[] = [
  { key: "page", header: "Page", primary: true, cell: (p) => <span className="font-mono text-xs text-ink">{p.page}</span> },
  { key: "clicks", header: "Clicks", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.clicks}</span> },
  { key: "impressions", header: "Impressions", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.impressions.toLocaleString()}</span> },
  { key: "position", header: "Position", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.position.toFixed(1)}</span> },
  { key: "delta", header: "Δ", align: "right", cell: (p) => <span className={cn("font-mono text-xs tnum", p.delta > 0 ? "text-success" : p.delta < 0 ? "text-danger" : "text-ink-faint")}>{p.delta > 0 ? "+" : ""}{p.delta}</span> },
];

function GscSection() {
  const { filters, isFiltered } = useSnapshot();
  const pages = applyGlobalFilters(useSeoLive(seoAgentApi.getGscPages, gscPages), filters);
  const kpis: MinimalKpi[] = [
    { label: "Pages tracked", value: String(pages.length) },
    { label: "Total clicks", value: pages.reduce((s, p) => s + p.clicks, 0).toLocaleString() },
    { label: "Impressions", value: pages.reduce((s, p) => s + p.impressions, 0).toLocaleString() },
    { label: "Gaining", value: String(pages.filter((p) => p.delta > 0).length), tone: "success" },
  ];
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex justify-end"><SnapshotBadge active={isFiltered} label="Global / site-wide" /></div>
      <DataPreviewTable columns={gscCols} rows={pages} rowKey={(p) => p.page} empty={noMatch} />
    </div>
  );
}

/* --------------------------------- Indexing --------------------------------- */

const indexCols: PreviewColumn<IndexRow>[] = [
  { key: "url", header: "URL", primary: true, cell: (r) => <span className="font-mono text-xs text-ink">{r.url}</span> },
  { key: "state", header: "State", cell: (r) => <StatusBadge tone={indexStateTone[r.state]} dot={false}>{r.state}</StatusBadge> },
  { key: "checked", header: "Last checked", cell: (r) => <span className="whitespace-nowrap text-xs text-ink-muted">{r.lastChecked}</span> },
  { key: "action", header: "Suggested action", cell: (r) => <span className="text-xs text-ink-faint">{r.action}</span> },
];

type IndexTab = "all" | "indexed" | "submitted" | "crawled" | "failed";
const INDEX_FILTERS: Record<IndexTab, (r: IndexRow) => boolean> = {
  all: () => true,
  indexed: (r) => r.state === "Indexed",
  submitted: (r) => r.state === "Submitted",
  crawled: (r) => r.state === "Crawled — not indexed",
  failed: (r) => r.state === "Failed",
};
const INDEX_LABELS: { id: IndexTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "indexed", label: "Indexed" },
  { id: "submitted", label: "Submitted" },
  { id: "crawled", label: "Not indexed" },
  { id: "failed", label: "Failed" },
];

function IndexingSection() {
  const { filters, isFiltered } = useSnapshot();
  const [tab, setTab] = useState<IndexTab>("all");
  const queue = applyGlobalFilters(useSeoLive(seoAgentApi.getIndexing, indexingQueue), filters);
  const kpis: MinimalKpi[] = [
    { label: "Indexed", value: String(queue.filter(INDEX_FILTERS.indexed).length), tone: "success" },
    { label: "Submitted", value: String(queue.filter(INDEX_FILTERS.submitted).length), tone: "info" },
    { label: "Not indexed", value: String(queue.filter(INDEX_FILTERS.crawled).length), tone: "warning" },
    { label: "Failed", value: String(queue.filter(INDEX_FILTERS.failed).length), tone: "danger" },
  ];
  const tabs: WorkflowTab[] = INDEX_LABELS.map((t) => ({ id: t.id, label: t.label, count: queue.filter(INDEX_FILTERS[t.id]).length }));
  const rows = queue.filter(INDEX_FILTERS[tab]);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as IndexTab)} isFiltered={isFiltered} />
      <DataPreviewTable columns={indexCols} rows={rows} rowKey={(r) => r.url} empty={noMatch} />
    </div>
  );
}

/* ----------------------------- Content pipeline ----------------------------- */

type ContentTab = "all" | "Todo" | "In Progress" | "Needs Review" | "Done";
const CONTENT_LABELS: { id: ContentTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "Needs Review", label: "Needs review" },
  { id: "In Progress", label: "In progress" },
  { id: "Todo", label: "To do" },
  { id: "Done", label: "Done" },
];

function ContentPipelineSection() {
  const { filters, isFiltered } = useSnapshot();
  const [tab, setTab] = useState<ContentTab>("all");
  const tasks = applyGlobalFilters(useSeoLive(seoAgentApi.getContentTasks, seoTasks), filters);
  const kpis: MinimalKpi[] = [
    { label: "Total tasks", value: String(tasks.length) },
    { label: "Needs review", value: String(tasks.filter((t) => t.status === "Needs Review").length), tone: "warning" },
    { label: "In progress", value: String(tasks.filter((t) => t.status === "In Progress").length), tone: "info" },
    { label: "Approval-gated", value: String(tasks.filter((t) => t.approvalRequired).length), tone: "rose" },
  ];
  const tabs: WorkflowTab[] = CONTENT_LABELS.map((t) => ({
    id: t.id, label: t.label,
    count: t.id === "all" ? tasks.length : tasks.filter((x) => x.status === t.id).length,
  }));
  const rows = tab === "all" ? tasks : tasks.filter((t) => t.status === tab);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as ContentTab)} isFiltered={isFiltered} />
      {rows.length === 0 ? noMatch : (
        <RecordList>
          {rows.map((t) => (
            <CompactRecordCard
              key={t.id}
              title={t.task}
              status={{ label: t.priority, tone: priorityTone[t.priority] }}
              fields={[
                { label: "Agent", value: t.agent },
                { label: "Page", value: <span className="font-mono text-xs">{t.url}</span> },
                { label: "Suggested action", value: t.suggestedAction },
              ]}
              meta={<StatusBadge tone={t.status === "Done" ? "success" : t.status === "Needs Review" ? "warning" : "info"} dot={false}>{t.status}</StatusBadge>}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ----------------------------- Hyperlocal pages ----------------------------- */

type HyperTab = "all" | "Published" | "Awaiting Approval" | "Draft" | "Duplicate Risk";
const HYPER_LABELS: { id: HyperTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "Published", label: "Published" },
  { id: "Awaiting Approval", label: "Awaiting approval" },
  { id: "Draft", label: "Draft" },
  { id: "Duplicate Risk", label: "Duplicate risk" },
];

function HyperlocalSection() {
  const { filters, isFiltered } = useSnapshot();
  const [tab, setTab] = useState<HyperTab>("all");
  const pages = applyGlobalFilters(useSeoLive(seoAgentApi.getHyperlocal, hyperlocalPages), filters);
  const kpis: MinimalKpi[] = [
    { label: "Area pages", value: String(pages.length) },
    { label: "Published", value: String(pages.filter((p) => p.status === "Published").length), tone: "success" },
    { label: "Awaiting approval", value: String(pages.filter((p) => p.status === "Awaiting Approval").length), tone: "rose" },
    { label: "Duplicate risk", value: String(pages.filter((p) => p.status === "Duplicate Risk").length), tone: "danger" },
  ];
  const tabs: WorkflowTab[] = HYPER_LABELS.map((t) => ({
    id: t.id, label: t.label,
    count: t.id === "all" ? pages.length : pages.filter((p) => p.status === t.id).length,
  }));
  const rows = tab === "all" ? pages : pages.filter((p) => p.status === tab);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as HyperTab)} isFiltered={isFiltered} />
      {rows.length === 0 ? noMatch : (
        <RecordList>
          {rows.map((p) => (
            <CompactRecordCard
              key={p.area}
              title={p.area}
              status={{ label: p.status, tone: hyperlocalStatusTone[p.status] }}
              fields={[
                { label: "City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.city}</span> },
                { label: "Words", value: String(p.wordCount) },
                { label: "Duplicate", value: `${p.duplicateScore}%` },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ------------------------------- Technical SEO ------------------------------ */

const techCols: PreviewColumn<TechSeoIssue>[] = [
  { key: "issue", header: "Issue", primary: true, cell: (t) => <span className="text-ink">{t.issue}</span> },
  { key: "type", header: "Type", cell: (t) => <span className="text-xs text-ink-muted">{t.type}</span> },
  { key: "affected", header: "Affected", align: "right", cell: (t) => <span className="font-mono text-sm text-ink tnum">{t.affected}</span> },
  { key: "severity", header: "Severity", cell: (t) => <StatusBadge tone={techSeoSeverityTone[t.severity]} dot={false}>{t.severity}</StatusBadge> },
  { key: "status", header: "Status", cell: (t) => <StatusBadge tone={t.status === "Resolved" ? "success" : t.status === "Monitoring" ? "info" : "warning"} dot={false}>{t.status}</StatusBadge> },
];

type TechTab = "all" | "Open" | "Monitoring" | "Resolved";
const TECH_LABELS: { id: TechTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "Open", label: "Open" },
  { id: "Monitoring", label: "Monitoring" },
  { id: "Resolved", label: "Resolved" },
];

function TechnicalSeoSection() {
  const { filters, isFiltered } = useSnapshot();
  const [tab, setTab] = useState<TechTab>("all");
  const issues = applyGlobalFilters(useSeoLive(seoAgentApi.getTechnicalIssues, techSeoIssues), filters);
  const kpis: MinimalKpi[] = [
    { label: "Total issues", value: String(issues.length) },
    { label: "Open", value: String(issues.filter((i) => i.status === "Open").length), tone: "warning" },
    { label: "High severity", value: String(issues.filter((i) => i.severity === "High").length), tone: "danger" },
    { label: "Resolved", value: String(issues.filter((i) => i.status === "Resolved").length), tone: "success" },
  ];
  const tabs: WorkflowTab[] = TECH_LABELS.map((t) => ({
    id: t.id, label: t.label,
    count: t.id === "all" ? issues.length : issues.filter((i) => i.status === t.id).length,
  }));
  const rows = tab === "all" ? issues : issues.filter((i) => i.status === tab);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as TechTab)} isFiltered={isFiltered} />
      <DataPreviewTable columns={techCols} rows={rows} rowKey={(t) => t.issue} empty={noMatch} />
    </div>
  );
}

/* -------------------------------- Competitors ------------------------------- */

const movementTone: Record<Competitor["movement"], Tone> = { up: "success", down: "danger", flat: "neutral" };
const movementLabel: Record<Competitor["movement"], string> = { up: "Gaining", down: "Losing", flat: "Steady" };
const MovementIcon = { up: TrendingUp, down: TrendingDown, flat: Minus };

function CompetitorsSection() {
  const { filters, isFiltered } = useSnapshot();
  const rows = applyGlobalFilters(useSeoLive(seoAgentApi.getCompetitors, competitors), filters);
  const kpis: MinimalKpi[] = [
    { label: "Competitors tracked", value: String(rows.length) },
    { label: "Gaining on us", value: String(rows.filter((c) => c.movement === "up").length), tone: "danger" },
    { label: "Losing ground", value: String(rows.filter((c) => c.movement === "down").length), tone: "success" },
  ];
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex justify-end"><SnapshotBadge active={isFiltered} label="Global / site-wide" /></div>
      {rows.length === 0 ? noMatch : (
        <RecordList>
          {rows.map((c) => {
            const Icon = MovementIcon[c.movement];
            return (
              <CompactRecordCard
                key={c.name}
                title={<span className="inline-flex items-center gap-2"><Icon className="h-4 w-4 text-ink-faint" />{c.name}</span>}
                status={{ label: movementLabel[c.movement], tone: movementTone[c.movement] }}
                fields={[
                  { label: "Change", value: c.change },
                  { label: "Detail", value: c.detail },
                ]}
              />
            );
          })}
        </RecordList>
      )}
    </div>
  );
}

/* --------------------------------- AI search -------------------------------- */

const aiCols: PreviewColumn<AiSearchRow>[] = [
  { key: "query", header: "Query", primary: true, cell: (a) => <span className="text-ink">{a.query}</span> },
  { key: "presence", header: "Presence", cell: (a) => <StatusBadge tone={aiPresenceTone[a.presence]} dot={false}>{a.presence}</StatusBadge> },
  { key: "engine", header: "Engine", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.engine}</span> },
  { key: "opportunity", header: "Opportunity", cell: (a) => <span className="text-xs text-ink-faint">{a.opportunity}</span> },
];

type AiTab = "all" | "Cited" | "Mentioned" | "Absent";
const AI_LABELS: { id: AiTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "Cited", label: "Cited" },
  { id: "Mentioned", label: "Mentioned" },
  { id: "Absent", label: "Absent" },
];

function AiSearchSection() {
  const { filters, isFiltered } = useSnapshot();
  const [tab, setTab] = useState<AiTab>("all");
  const rows = applyGlobalFilters(useSeoLive(seoAgentApi.getAiSearch, aiSearch), filters);
  const kpis: MinimalKpi[] = [
    { label: "Queries tracked", value: String(rows.length) },
    { label: "Cited", value: String(rows.filter((a) => a.presence === "Cited").length), tone: "success" },
    { label: "Mentioned", value: String(rows.filter((a) => a.presence === "Mentioned").length), tone: "info" },
    { label: "Absent", value: String(rows.filter((a) => a.presence === "Absent").length), tone: "warning" },
  ];
  const tabs: WorkflowTab[] = AI_LABELS.map((t) => ({
    id: t.id, label: t.label,
    count: t.id === "all" ? rows.length : rows.filter((a) => a.presence === t.id).length,
  }));
  const filtered = tab === "all" ? rows : rows.filter((a) => a.presence === tab);
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as AiTab)} isFiltered={isFiltered} />
      <DataPreviewTable columns={aiCols} rows={filtered} rowKey={(a) => a.query} empty={noMatch} />
    </div>
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
    <div className="space-y-6">
      <BriefCard />
      <div className="space-y-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Scheduled reports</p>
        <RecordList>
          {reports.map((r) => (
            <CompactRecordCard
              key={r.name}
              title={r.name}
              status={{ label: r.freq, tone: "neutral" }}
              fields={[{ label: "Summary", value: r.summary }]}
              meta={<FileText className="h-4 w-4 text-ink-faint" />}
            />
          ))}
        </RecordList>
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
