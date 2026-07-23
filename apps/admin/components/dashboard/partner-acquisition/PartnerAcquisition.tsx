"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  SearchX, Send, CalendarClock, ShieldCheck, Globe2, Gauge, Info, MapPin,
} from "lucide-react";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { Tone } from "@/lib/dashboard/types";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, DataPreviewTable,
  EmptyState, StatusBadge, SnapshotBadge,
  type MinimalKpi, type WorkflowTab, type PreviewColumn,
} from "@/components/dashboard/minimal";
import {
  roleCards, roleStatusTone,
  partners, stageTone, complianceTone, getPartnerIdByName,
  marketIntel, readinessTone,
  outreach,
  meetings, meetingStatusTone,
  complianceQueue,
  regionalCoverage, coverageStatusTone,
  performancePreview,
  type Partner, type PipelineStage,
  type MarketRow, type OutreachRow, type CoverageRow, type PerformancePreviewRow,
} from "@/lib/dashboard/partner-acquisition-data";

/* -------------------------------- shared bits ------------------------------- */

function scoreTone(n: number): Tone {
  return n >= 80 ? "success" : n >= 65 ? "rose" : n >= 45 ? "warning" : "neutral";
}

function TabsRow({ tabs, value, onChange }: { tabs: WorkflowTab[]; value: string; onChange: (id: string) => void }) {
  const { filters } = useFilters();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <WorkflowTabs tabs={tabs} value={value} onChange={onChange} />
      <SnapshotBadge active={activeFilterCount(filters) > 0} />
    </div>
  );
}

function InfoNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
      <p className="text-xxs leading-relaxed text-ink-muted">{children}</p>
    </div>
  );
}

const num = (n: number) => String(n);

/* ------------------------------ Team & ownership ---------------------------- */

function TeamSection() {
  const totalPipeline = roleCards.reduce((s, r) => s + r.pipeline, 0);
  const activeTasks = roleCards.reduce((s, r) => s + r.activeTasks, 0);
  const meetingsWk = roleCards.reduce((s, r) => s + r.meetingsThisWeek, 0);
  const onTrack = roleCards.filter((r) => r.status !== "At risk").length;

  const kpis: MinimalKpi[] = [
    { label: "Roles on track", value: `${onTrack} / ${roleCards.length}` },
    { label: "Total pipeline", value: num(totalPipeline) },
    { label: "Active tasks", value: num(activeTasks) },
    { label: "Meetings this week", value: num(meetingsWk) },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <InfoNote>
        <span className="font-semibold text-ink">Business data only.</span> No live CRM connected — role cards show
        ownership and workload, never private personal emails or phone numbers.
      </InfoNote>
      <RecordList>
        {roleCards.map((r) => (
          <CompactRecordCard
            key={r.role}
            title={r.role}
            status={{ label: r.status, tone: roleStatusTone[r.status] }}
            fields={[
              { label: "Owner", value: r.owner },
              { label: "Region", value: <span className="inline-flex items-center gap-1"><Globe2 className="h-3 w-3 text-ink-faint" />{r.region}</span> },
              { label: "Target", value: r.targets },
            ]}
            meta={
              <span className="flex flex-col items-end gap-1">
                <span className="font-mono text-sm text-ink tnum">{r.pipeline}</span>
                <span className="text-xxs text-ink-faint">in pipeline</span>
              </span>
            }
          />
        ))}
      </RecordList>
    </div>
  );
}

/* ------------------------------ Partner pipeline ---------------------------- */

type PipeTabId = "all" | "new" | "qualified" | "proposal" | "onboarding" | "active" | "rejected";

const STAGE_GROUPS: Record<PipeTabId, (s: PipelineStage) => boolean> = {
  all: () => true,
  new: (s) => s === "New Lead" || s === "Researching" || s === "Contacted",
  qualified: (s) => s === "Qualified" || s === "Meeting Scheduled",
  proposal: (s) => s === "Proposal Sent" || s === "Contract Sent",
  onboarding: (s) => s === "Compliance Review" || s === "Onboarding",
  active: (s) => s === "Active Partner",
  rejected: (s) => s === "Rejected / Not Fit",
};

const PIPE_TABS: { id: PipeTabId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "new", label: "New" },
  { id: "qualified", label: "Qualifying" },
  { id: "proposal", label: "Proposal" },
  { id: "onboarding", label: "Onboarding" },
  { id: "active", label: "Active" },
  { id: "rejected", label: "Rejected" },
];

const isPipeTab = (v: string | null): v is PipeTabId => !!v && v in STAGE_GROUPS;

function PipelineSection() {
  const router = useRouter();
  const search = useSearchParams();
  const { filters } = useFilters();
  const initial = search.get("tab");
  const [tab, setTab] = useState<PipeTabId>(isPipeTab(initial) ? initial : "all");

  const base = useMemo(() => applyGlobalFilters(partners, filters), [filters]);
  const rows = base.filter((p) => STAGE_GROUPS[tab](p.stage));

  const kpis: MinimalKpi[] = [
    { label: "Partner leads", value: num(base.length) },
    { label: "Active partners", value: num(base.filter((p) => STAGE_GROUPS.active(p.stage)).length), tone: "success" },
    { label: "In onboarding", value: num(base.filter((p) => STAGE_GROUPS.onboarding(p.stage)).length) },
    { label: "Needs compliance", value: num(base.filter((p) => p.compliance === "Docs Pending" || p.compliance === "Flagged").length), tone: "warning" },
  ];

  const tabs: WorkflowTab[] = PIPE_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter((p) => STAGE_GROUPS[t.id](p.stage)).length }));
  const openLead = (p: Partner) => router.push(`/partner-acquisition/pipeline/${p.id}?tab=${tab}`);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as PipeTabId)} />
      {rows.length === 0 ? (
        <EmptyState icon={SearchX} title="No partners in this view" description="No leads match this stage and the active filters." />
      ) : (
        <RecordList>
          {rows.map((p) => (
            <CompactRecordCard
              key={p.id}
              id={p.id}
              title={p.name}
              status={{ label: p.stage, tone: stageTone[p.stage] }}
              fields={[
                { label: "Type", value: p.type },
                { label: "Location", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.city}, {p.country}</span> },
                { label: "Owner", value: p.owner },
              ]}
              meta={
                <span className="flex flex-col items-end gap-1">
                  <StatusBadge tone={scoreTone(p.score)} dot={false}>{p.score}</StatusBadge>
                  <span className="text-xxs text-ink-faint">score</span>
                </span>
              }
              onClick={() => openLead(p)}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ----------------------------- Market intelligence -------------------------- */

function MarketSection() {
  const { filters } = useFilters();
  const rows = useMemo(() => applyGlobalFilters(marketIntel, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;
  const priority = rows.filter((m) => m.readiness === "Priority").length;
  const avg = rows.length ? Math.round(rows.reduce((s, m) => s + m.opportunity, 0) / rows.length) : 0;
  const top = rows.length ? [...rows].sort((a, b) => b.opportunity - a.opportunity)[0] : undefined;

  const kpis: MinimalKpi[] = [
    { label: "Cities tracked", value: num(rows.length) },
    { label: "Priority markets", value: num(priority), tone: priority > 0 ? "rose" : "neutral" },
    { label: "Avg opportunity", value: num(avg) },
    { label: "Top city", value: top ? top.city : "—" },
  ];

  const cols: PreviewColumn<MarketRow>[] = [
    { key: "country", header: "Country", primary: true, cell: (m) => <span className="font-medium text-ink">{m.country}</span> },
    { key: "city", header: "City", cell: (m) => <span className="text-ink-muted">{m.city}</span> },
    { key: "opp", header: "Opportunity", align: "right", cell: (m) => <span className="font-mono text-sm text-ink tnum">{m.opportunity}</span> },
    { key: "readiness", header: "Readiness", cell: (m) => <StatusBadge tone={readinessTone[m.readiness]} dot={false}>{m.readiness}</StatusBadge> },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex justify-end"><SnapshotBadge active={isFiltered} /></div>
      <DataPreviewTable
        columns={cols}
        rows={rows}
        rowKey={(m) => m.city}
        empty={<EmptyState icon={SearchX} title="No cities match the filters" description="Try clearing a filter to see more markets." />}
      />
    </div>
  );
}

/* ------------------------------ Outreach tracker ---------------------------- */

function OutreachSection() {
  const { filters } = useFilters();
  const rows = useMemo(() => applyGlobalFilters(outreach, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;
  const totals = rows.reduce((a, o) => ({ sent: a.sent + o.sent, replies: a.replies + o.replies, meetings: a.meetings + o.meetings, followups: a.followups + o.followupsDue }), { sent: 0, replies: 0, meetings: 0, followups: 0 });

  const kpis: MinimalKpi[] = [
    { label: "Outreach sent", value: num(totals.sent) },
    { label: "Replies", value: num(totals.replies) },
    { label: "Meetings booked", value: num(totals.meetings) },
    { label: "Follow-ups due", value: num(totals.followups), tone: totals.followups > 0 ? "warning" : "neutral" },
  ];

  const cols: PreviewColumn<OutreachRow>[] = [
    { key: "region", header: "Region", primary: true, cell: (o) => <span className="font-medium text-ink">{o.region}</span> },
    { key: "sent", header: "Sent", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{o.sent}</span> },
    { key: "replies", header: "Replies", align: "right", cell: (o) => <span className="font-mono text-sm text-ink-muted tnum">{o.replies}</span> },
    { key: "rate", header: "Response rate", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{o.responseRate.toFixed(1)}%</span> },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex justify-end"><SnapshotBadge active={isFiltered} /></div>
      <DataPreviewTable
        columns={cols}
        rows={rows}
        rowKey={(o) => o.region}
        empty={<EmptyState icon={Send} title="No outreach in this view" description="No regions match the active filters." />}
      />
    </div>
  );
}

/* --------------------------- Meetings & follow-ups -------------------------- */

type MeetTabId = "all" | "scheduled" | "confirmed" | "awaiting" | "done";
const MEET_TABS: { id: MeetTabId; label: string; match: (s: string) => boolean }[] = [
  { id: "all", label: "All", match: () => true },
  { id: "scheduled", label: "Scheduled", match: (s) => s === "Scheduled" },
  { id: "confirmed", label: "Confirmed", match: (s) => s === "Confirmed" },
  { id: "awaiting", label: "Awaiting reply", match: (s) => s === "Awaiting Reply" },
  { id: "done", label: "Done", match: (s) => s === "Done" },
];

function MeetingsSection() {
  const router = useRouter();
  const { filters } = useFilters();
  const [tab, setTab] = useState<MeetTabId>("all");
  const base = useMemo(() => applyGlobalFilters(meetings, filters), [filters]);
  const matcher = MEET_TABS.find((t) => t.id === tab)!.match;
  const rows = base.filter((m) => matcher(m.status));

  const kpis: MinimalKpi[] = [
    { label: "Upcoming", value: num(base.filter((m) => m.status !== "Done").length) },
    { label: "Confirmed", value: num(base.filter((m) => m.status === "Confirmed").length), tone: "success" },
    { label: "Awaiting reply", value: num(base.filter((m) => m.status === "Awaiting Reply").length), tone: "warning" },
    { label: "Done", value: num(base.filter((m) => m.status === "Done").length) },
  ];
  const tabs: WorkflowTab[] = MEET_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter((m) => t.match(m.status)).length }));

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as MeetTabId)} />
      {rows.length === 0 ? (
        <EmptyState icon={CalendarClock} title="No meetings in this view" description="No meetings match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((m) => {
            const leadId = getPartnerIdByName(m.partner);
            return (
              <CompactRecordCard
                key={m.id}
                id={m.id}
                title={m.partner}
                status={{ label: m.status, tone: meetingStatusTone[m.status] }}
                fields={[
                  { label: "Type", value: m.type },
                  { label: "When", value: new Date(m.datetime).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
                  { label: "Owner", value: m.owner },
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

/* ------------------------------ Compliance queue ---------------------------- */

type CompTabId = "all" | "in-review" | "docs-pending" | "flagged" | "passed";
const COMP_TABS: { id: CompTabId; label: string; match: (s: string) => boolean }[] = [
  { id: "all", label: "All", match: () => true },
  { id: "in-review", label: "In review", match: (s) => s === "In Review" },
  { id: "docs-pending", label: "Docs pending", match: (s) => s === "Docs Pending" },
  { id: "flagged", label: "Flagged", match: (s) => s === "Flagged" },
  { id: "passed", label: "Passed", match: (s) => s === "Passed" },
];

function ComplianceSection() {
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
  const tabs: WorkflowTab[] = COMP_TABS.map((t) => ({ id: t.id, label: t.label, count: base.filter((c) => t.match(c.status)).length }));

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <InfoNote>
        <span className="font-semibold text-ink">Status-only view.</span> Trade licenses, bank details and documents are
        represented as states — no document contents or account numbers are stored.
      </InfoNote>
      <TabsRow tabs={tabs} value={tab} onChange={(id) => setTab(id as CompTabId)} />
      {rows.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="No compliance records in this view" description="No partners match this status and the active filters." />
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

/* ------------------------------ Regional coverage --------------------------- */

function CoverageSection() {
  const { filters } = useFilters();
  const rows = useMemo(() => applyGlobalFilters(regionalCoverage, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;
  const active = rows.reduce((s, c) => s + c.activePartners, 0);
  const pipeline = rows.reduce((s, c) => s + c.pipeline, 0);
  const covered = rows.reduce((s, c) => s + c.covered, 0);
  const gaps = rows.filter((c) => c.status === "Gap" || c.status === "Early").length;

  const kpis: MinimalKpi[] = [
    { label: "Active partners", value: num(active), tone: "success" },
    { label: "In pipeline", value: num(pipeline) },
    { label: "Markets covered", value: num(covered) },
    { label: "Coverage gaps", value: num(gaps), tone: gaps > 0 ? "warning" : "neutral" },
  ];

  const cols: PreviewColumn<CoverageRow>[] = [
    { key: "region", header: "Region", primary: true, cell: (c) => <span className="font-medium text-ink">{c.region}</span> },
    { key: "active", header: "Active", align: "right", cell: (c) => <span className="font-mono text-sm text-ink tnum">{c.activePartners}</span> },
    { key: "pipeline", header: "Pipeline", align: "right", cell: (c) => <span className="font-mono text-sm text-ink-muted tnum">{c.pipeline}</span> },
    { key: "coverage", header: "Coverage", align: "right", cell: (c) => <span className="font-mono text-sm text-ink-muted tnum">{c.covered}/{c.targetMarkets}</span> },
    { key: "status", header: "Status", cell: (c) => <StatusBadge tone={coverageStatusTone[c.status]} dot={false}>{c.status}</StatusBadge> },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex justify-end"><SnapshotBadge active={isFiltered} /></div>
      <DataPreviewTable
        columns={cols}
        rows={rows}
        rowKey={(c) => c.region}
        empty={<EmptyState icon={Globe2} title="No regions match the filters" description="Try clearing a filter to see more coverage." />}
      />
    </div>
  );
}

/* -------------------------- Partner performance preview --------------------- */

function PerformanceSection() {
  const { filters } = useFilters();
  const rows = useMemo(() => applyGlobalFilters(performancePreview, filters), [filters]);
  const orders = rows.reduce((s, p) => s + p.ordersHandled, 0);
  const avgQuality = rows.length ? Math.round(rows.reduce((s, p) => s + p.qualityScore, 0) / rows.length) : 0;

  const kpis: MinimalKpi[] = [
    { label: "Onboarded partners", value: num(rows.length) },
    { label: "Orders handled", value: num(orders) },
    { label: "Avg quality", value: num(avgQuality), tone: avgQuality >= 90 ? "success" : "neutral" },
    { label: "Data source", value: "Preview", hint: "Streams from Operations once live" },
  ];

  const cols: PreviewColumn<PerformancePreviewRow>[] = [
    { key: "partner", header: "Partner", primary: true, cell: (p) => <span className="font-medium text-ink">{p.partner}</span> },
    { key: "city", header: "City", cell: (p) => <span className="text-ink-muted">{p.city}</span> },
    { key: "orders", header: "Orders", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.ordersHandled}</span> },
    { key: "quality", header: "Quality", align: "right", cell: (p) => <StatusBadge tone={scoreTone(p.qualityScore)} dot={false}>{p.qualityScore}</StatusBadge> },
    { key: "revenue", header: "Revenue share", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.revenueShare.toFixed(1)}%</span> },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <InfoNote>
        <span className="font-semibold text-ink">Preview.</span> Full partner performance streams in from Operations once
        onboarded partners handle live volume. Onboarded partners shown as a preview.
      </InfoNote>
      <DataPreviewTable
        columns={cols}
        rows={rows}
        rowKey={(p) => p.partner}
        empty={<EmptyState icon={Gauge} title="No onboarded partners yet" description="Performance appears here once partners go live." />}
      />
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Partner Acquisition subsection by slug (see lib/dashboard/sections.ts). */
export function PartnerSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "team": return <TeamSection />;
    case "pipeline": return <PipelineSection />;
    case "market-intelligence": return <MarketSection />;
    case "outreach": return <OutreachSection />;
    case "meetings": return <MeetingsSection />;
    case "compliance-queue": return <ComplianceSection />;
    case "regional-coverage": return <CoverageSection />;
    case "performance-preview": return <PerformanceSection />;
    default: return <TeamSection />;
  }
}
