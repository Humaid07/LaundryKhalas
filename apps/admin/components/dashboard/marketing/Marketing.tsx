"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, CalendarDays, Users, Mail, SearchX, ShieldCheck } from "lucide-react";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { CreativeStudio } from "@/components/dashboard/CreativeStudio";
import {
  platformStats,
  marketingKpis,
  contentCalendar,
  marketingApprovals,
  marketingAgents,
  campaignLinks,
} from "@/lib/dashboard/mock-data";
import {
  socialDrafts,
  socialDraftStatusTone,
  campaigns,
  campaignStatusTone,
  prItems,
  campaignHref,
  approvalHref,
  type SocialDraft,
  type Campaign,
  type PrItem,
} from "@/lib/dashboard/marketing-data";
import { formatCurrency, formatNumber } from "@/lib/dashboard/formatters";
import { marketingStatusTone } from "@/lib/dashboard/status-maps";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, DataPreviewTable,
  EmptyState, StatusBadge, SnapshotBadge,
  type MinimalKpi, type WorkflowTab, type PreviewColumn,
} from "@/components/dashboard/minimal";

/* Shared empty state for filtered-out marketing lists/tables. */
const noMatch = (
  <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />
);

/** Small brand-wide snapshot marker for non-geo marketing views. */
function SnapshotOnly() {
  const { filters } = useFilters();
  return (
    <div className="flex justify-end">
      <SnapshotBadge active={activeFilterCount(filters) > 0} label="Brand-wide" />
    </div>
  );
}

/* -------------------------------- Overview ---------------------------------- */

const channelCols: PreviewColumn<(typeof platformStats)[number]>[] = [
  { key: "platform", header: "Channel", primary: true, cell: (p) => <span className="font-medium text-ink">{p.platform}</span> },
  { key: "followers", header: "Followers", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{formatNumber(p.followers, true)}</span> },
  { key: "engagement", header: "Engagement", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{p.engagement}%</span> },
  { key: "leads", header: "Leads", align: "right", cell: (p) => <span className="font-mono font-semibold text-rose tnum">{formatNumber(p.leads)}</span> },
];

const agentCols: PreviewColumn<(typeof marketingAgents)[number]>[] = [
  { key: "name", header: "Agent", primary: true, cell: (a) => <span className="font-medium text-ink">{a.name}</span> },
  { key: "status", header: "Status", cell: (a) => <StatusBadge tone={marketingStatusTone[a.status] ?? "neutral"} dot={false}>{a.status}</StatusBadge> },
  { key: "note", header: "Latest", cell: (a) => <span className="text-ink-muted">{a.note}</span> },
];

function OverviewTab() {
  const kpis: MinimalKpi[] = marketingKpis.slice(0, 4).map((k) => ({ label: k.label, value: String(k.value), tone: k.tone }));
  return (
    <div className="space-y-6">
      <SnapshotOnly />
      <MinimalKpiStrip kpis={kpis} />
      <div className="space-y-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Connected channels</p>
        <DataPreviewTable columns={channelCols} rows={platformStats.filter((p) => p.connected)} rowKey={(p) => p.platform} />
      </div>
      <div className="space-y-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Marketing agents</p>
        <DataPreviewTable columns={agentCols} rows={marketingAgents} rowKey={(a) => a.name} />
      </div>
    </div>
  );
}

/* --------------------------- Platform analytics ----------------------------- */

const analyticsCols: PreviewColumn<(typeof platformStats)[number]>[] = [
  { key: "platform", header: "Platform", primary: true, cell: (p) => <span className="font-medium text-ink">{p.platform}</span> },
  { key: "followers", header: "Followers", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{formatNumber(p.followers, true)}</span> },
  { key: "reach", header: "Reach", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{formatNumber(p.reach, true)}</span> },
  { key: "engagement", header: "Engagement", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{p.engagement}%</span> },
  { key: "clicks", header: "Clicks", align: "right", cell: (p) => <span className="font-mono text-ink-muted tnum">{formatNumber(p.clicks, true)}</span> },
  { key: "leads", header: "Leads", align: "right", cell: (p) => <span className="font-mono font-semibold text-rose tnum">{formatNumber(p.leads)}</span> },
];

function PlatformAnalyticsTab() {
  const connected = platformStats.filter((p) => p.connected);
  const kpis: MinimalKpi[] = [
    { label: "Connected channels", value: String(connected.length) },
    { label: "Total reach", value: formatNumber(connected.reduce((s, p) => s + p.reach, 0), true) },
    { label: "Total clicks", value: formatNumber(connected.reduce((s, p) => s + p.clicks, 0), true) },
    { label: "Total leads", value: formatNumber(connected.reduce((s, p) => s + p.leads, 0)) },
  ];
  return (
    <div className="space-y-6">
      <SnapshotOnly />
      <MinimalKpiStrip kpis={kpis} />
      <DataPreviewTable columns={analyticsCols} rows={connected} rowKey={(p) => p.platform} />
    </div>
  );
}

/* --------------------------- Content calendar ------------------------------- */

type ContentPost = { platform: string; title: string; time: string; status: string; day: string };
const CONTENT_STATUSES = ["Scheduled", "Awaiting Approval", "Draft"] as const;

function ContentCalendarTab() {
  const posts: ContentPost[] = contentCalendar.flatMap((d) => d.posts.map((p) => ({ ...p, day: d.day })));
  const [tab, setTab] = useState<string>("all");

  const byStatus = (s: string) => posts.filter((p) => p.status === s);
  const kpis: MinimalKpi[] = [
    { label: "Scheduled", value: String(byStatus("Scheduled").length) },
    { label: "Awaiting approval", value: String(byStatus("Awaiting Approval").length), tone: "rose" },
    { label: "Drafts", value: String(byStatus("Draft").length) },
  ];

  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: posts.length },
    ...CONTENT_STATUSES.map((s) => ({ id: s, label: s, count: byStatus(s).length })),
  ];
  const rows = tab === "all" ? posts : posts.filter((p) => p.status === tab);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={setTab} />
        <SnapshotBadge active={false} label="This week" />
      </div>
      {rows.length === 0 ? (
        <EmptyState icon={CalendarDays} title="No posts in this view" description="Scheduled and pending posts for the week appear here." />
      ) : (
        <RecordList>
          {rows.map((p, i) => (
            <CompactRecordCard
              key={`${p.day}-${p.title}-${i}`}
              title={p.title}
              status={{ label: p.status, tone: marketingStatusTone[p.status] ?? "neutral" }}
              fields={[
                { label: "Platform", value: p.platform },
                { label: "Day", value: p.day },
                { label: "Time", value: p.time },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* -------------------------------- Social posting ---------------------------- */

const SOCIAL_STATUSES = ["Draft", "Awaiting Approval", "Scheduled"] as const;

function SocialPostingTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<string>("all");
  const base = useMemo(() => applyGlobalFilters(socialDrafts, filters), [filters]);

  const byStatus = (s: string) => base.filter((d) => d.status === s);
  const kpis: MinimalKpi[] = [
    { label: "Awaiting approval", value: String(byStatus("Awaiting Approval").length), tone: "rose" },
    { label: "Scheduled", value: String(byStatus("Scheduled").length), tone: "info" },
    { label: "Drafts", value: String(byStatus("Draft").length) },
  ];
  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    ...SOCIAL_STATUSES.map((s) => ({ id: s, label: s, count: byStatus(s).length })),
  ];
  const rows: SocialDraft[] = tab === "all" ? base : base.filter((d) => d.status === tab);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={setTab} />
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      {rows.length === 0 ? (
        noMatch
      ) : (
        <RecordList>
          {rows.map((d) => (
            <CompactRecordCard
              key={d.id}
              id={d.id}
              title={d.title}
              status={{ label: d.status, tone: socialDraftStatusTone[d.status] }}
              fields={[
                { label: "Platform", value: d.platform },
                { label: "Type", value: d.type },
                { label: "Scheduled", value: d.scheduledFor },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ---------------------------------- Campaigns ------------------------------- */

const CAMPAIGN_TABS = ["Active", "Scheduled", "Paused", "Ended"] as const;

function CampaignsTab() {
  const search = useSearchParams();
  const { filters } = useFilters();
  const initial = search.get("tab") ?? "all";
  const [tab, setTab] = useState<string>(initial);

  // `channel` on a campaign is a display grouping, not the global Channel dim.
  const base = useMemo(() => applyGlobalFilters(campaigns, { ...filters, channel: "" }), [filters]);
  const byStatus = (s: string) => base.filter((c) => c.status === s);

  const kpis: MinimalKpi[] = [
    { label: "Active", value: String(byStatus("Active").length), tone: "success" },
    { label: "Total spend", value: formatCurrency(base.reduce((s, c) => s + c.spend, 0)) },
    { label: "Leads", value: String(base.reduce((s, c) => s + c.leads, 0)) },
    { label: "Reach", value: formatNumber(base.reduce((s, c) => s + c.reach, 0), true) },
  ];
  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    ...CAMPAIGN_TABS.map((s) => ({ id: s, label: s, count: byStatus(s).length })),
  ];
  const rows: Campaign[] = tab === "all" ? base : base.filter((c) => c.status === tab);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={setTab} />
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      {rows.length === 0 ? (
        noMatch
      ) : (
        <RecordList>
          {rows.map((c) => (
            <CompactRecordCard
              key={c.id}
              id={c.id}
              title={c.name}
              status={{ label: c.status, tone: campaignStatusTone[c.status] }}
              fields={[
                { label: "Channels", value: c.channel },
                { label: "Spend", value: formatCurrency(c.spend) },
                { label: "Leads", value: String(c.leads) },
              ]}
              meta={<span className="hidden text-xxs text-ink-faint sm:block">ROAS {c.roas}</span>}
              href={campaignHref(c.id, tab)}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* -------------------------------- Approvals --------------------------------- */

function ApprovalsTab() {
  const kpis: MinimalKpi[] = [
    { label: "Awaiting approval", value: String(marketingApprovals.filter((m) => m.status === "Awaiting Approval").length), tone: "rose" },
    { label: "Changes requested", value: String(marketingApprovals.filter((m) => m.status === "Changes Requested").length), tone: "warning" },
    { label: "Total pending", value: String(marketingApprovals.length) },
  ];
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      {marketingApprovals.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="Nothing awaiting approval" description="Agent-drafted content pending a human sign-off appears here." />
      ) : (
        <RecordList>
          {marketingApprovals.map((m) => (
            <CompactRecordCard
              key={m.id}
              id={m.id}
              title={m.caption}
              status={{ label: m.status, tone: marketingStatusTone[m.status] ?? "neutral" }}
              fields={[
                { label: "Platform", value: m.platform },
                { label: "Asset", value: m.assetType },
                { label: "By", value: m.createdBy },
              ]}
              href={approvalHref(m.id)}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ------------------------------ Influencer / UGC ---------------------------- */

interface Creator {
  name: string;
  followers: string;
  niche: string;
  status: string;
  /** City the creator's audience is based in (drives the global geo filters). */
  city: string;
}

const creators: Creator[] = [
  { name: "@dubai.home.edit", followers: "128K", niche: "Home & lifestyle", status: "Shortlisted", city: "Dubai" },
  { name: "@doha.mom.diaries", followers: "64K", niche: "Family", status: "Shortlisted", city: "Doha" },
  { name: "@riyadh.style", followers: "212K", niche: "Fashion", status: "Contacted (draft)", city: "Riyadh" },
];

function InfluencerTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(creators, filters);
  return (
    <div className="space-y-6">
      <SnapshotOnly />
      {rows.length === 0 ? (
        <EmptyState icon={Users} title="No creators match the selected filters" description="Creator shortlist — outreach is drafted, never sent automatically." />
      ) : (
        <RecordList>
          {rows.map((c) => (
            <CompactRecordCard
              key={c.name}
              title={c.name}
              status={{ label: c.status, tone: c.status === "Shortlisted" ? "info" : "warning" }}
              fields={[
                { label: "Followers", value: c.followers },
                { label: "Niche", value: c.niche },
                { label: "City", value: c.city },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* -------------------------------- PR & outreach ----------------------------- */

const PR_TABS = ["Draft", "Ready to Send", "Held"] as const;
const prTone = (s: PrItem["status"]) => (s === "Ready to Send" ? "success" : s === "Held" ? "warning" : "neutral");

function PrOutreachTab() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<string>("all");
  const base = useMemo(() => applyGlobalFilters(prItems, filters), [filters]);
  const byStatus = (s: string) => base.filter((p) => p.status === s);
  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    ...PR_TABS.map((s) => ({ id: s, label: s, count: byStatus(s).length })),
  ];
  const rows: PrItem[] = tab === "all" ? base : base.filter((p) => p.status === tab);

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs leading-relaxed text-ink-muted">
          <span className="font-semibold text-ink">Drafts only.</span> PR and outreach are drafted by the agent and held here — nothing sends without approval.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={setTab} />
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      {rows.length === 0 ? (
        <EmptyState icon={Mail} title="No drafts in this view" description="Drafted outreach and PR items appear here, held for approval." />
      ) : (
        <RecordList>
          {rows.map((p) => (
            <CompactRecordCard
              key={`${p.outlet}-${p.topic}`}
              title={p.outlet}
              status={{ label: p.status, tone: prTone(p.status) }}
              fields={[
                { label: "Type", value: p.type },
                { label: "Topic", value: p.topic },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* -------------------------------- UTM tracking ------------------------------ */

const utmCols: PreviewColumn<(typeof campaignLinks)[number]>[] = [
  { key: "name", header: "Campaign", primary: true, cell: (c) => <span className="font-medium text-ink">{c.name}</span> },
  { key: "source", header: "Source", cell: (c) => <span className="text-ink-muted">{c.source}</span> },
  { key: "utm", header: "UTM", cell: (c) => <span className="font-mono text-xs text-ink-faint">{c.utm}</span> },
  { key: "clicks", header: "Clicks", align: "right", cell: (c) => <span className="font-mono text-ink-muted tnum">{formatNumber(c.clicks)}</span> },
  { key: "leads", header: "Leads", align: "right", cell: (c) => <span className="font-mono font-semibold text-rose tnum">{formatNumber(c.leads)}</span> },
];

function UtmTrackingTab() {
  const kpis: MinimalKpi[] = [
    { label: "Tracked links", value: String(campaignLinks.length) },
    { label: "Total clicks", value: formatNumber(campaignLinks.reduce((s, c) => s + c.clicks, 0)) },
    { label: "Total leads", value: formatNumber(campaignLinks.reduce((s, c) => s + c.leads, 0)) },
  ];
  return (
    <div className="space-y-6">
      <SnapshotOnly />
      <MinimalKpiStrip kpis={kpis} />
      <DataPreviewTable columns={utmCols} rows={campaignLinks} rowKey={(c) => c.name} empty={noMatch} />
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Marketing subsection by slug (see lib/dashboard/sections.ts). */
export function MarketingSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "overview": return <OverviewTab />;
    case "platform-analytics": return <PlatformAnalyticsTab />;
    case "content-calendar": return <ContentCalendarTab />;
    case "creative-studio": return <CreativeStudio />;
    case "social-posting": return <SocialPostingTab />;
    case "campaigns": return <CampaignsTab />;
    case "approvals": return <ApprovalsTab />;
    case "influencer-ugc": return <InfluencerTab />;
    case "pr-outreach": return <PrOutreachTab />;
    case "utm-tracking": return <UtmTrackingTab />;
    default: return <OverviewTab />;
  }
}
