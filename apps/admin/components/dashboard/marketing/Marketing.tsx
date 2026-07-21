"use client";

import { Mail, Users, Check, X, Pencil, CalendarClock, Megaphone, SearchX } from "lucide-react";
import { SectionTitle } from "@/components/dashboard/shell/PageHeader";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { LineTrend } from "@/components/dashboard/charts";
import { PlatformMetricCard } from "@/components/dashboard/widgets";
import { CreativeStudio } from "@/components/dashboard/CreativeStudio";
import { LocalFilterBar, useLocalFilters, matchesLocal, type LocalFilterDef } from "@/components/dashboard/ui/LocalFilters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { CHART } from "@/lib/dashboard/chart-theme";
import {
  platformStats,
  marketingKpis,
  engagementTrend,
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
  SOCIAL_PLATFORMS,
  SOCIAL_DRAFT_STATUSES,
  CAMPAIGN_STATUSES,
  PR_STATUSES,
  type SocialDraft,
  type Campaign,
  type PrItem,
} from "@/lib/dashboard/marketing-data";
import { formatCurrency, formatNumber } from "@/lib/dashboard/formatters";
import { marketingStatusTone } from "@/lib/dashboard/status-maps";

/** Shared empty state for filtered-out marketing tables/lists. */
const noMatch = <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />;

/** Header row flagging brand-wide marketing views that are not geo-filtered. */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} label="Brand-wide" />
    </div>
  );
}

/* -------------------------------- Overview ---------------------------------- */

function SocialOverviewTab() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="Marketing overview" />
      <StatGrid stats={marketingKpis} cols="4" />
      <div>
        <SectionTitle title="Connected platforms" description="Followers, reach, engagement and leads per channel" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {platformStats.map((p) => (
            <PlatformMetricCard key={p.platform} platform={p} />
          ))}
        </div>
      </div>
      <div>
        <SectionTitle title="Marketing agents" description="Every posting & outreach agent runs behind a human approval gate" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {marketingAgents.map((a) => (
            <div key={a.name} className="flex items-start justify-between gap-3 rounded-2xl border border-border bg-surface p-4 shadow-card">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{a.name}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{a.note}</p>
                {a.approvalGate && (
                  <span className="mt-2 inline-flex items-center gap-1 rounded-md bg-rose/8 px-1.5 py-0.5 text-xxs font-semibold text-rose">Approval gate</span>
                )}
              </div>
              <StatusBadge tone={marketingStatusTone[a.status] ?? "neutral"}>{a.status}</StatusBadge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* --------------------------- Platform analytics ----------------------------- */

function PlatformAnalyticsTab() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="Platform analytics" />
      <ChartCard title="Engagement rate by platform" subtitle="Weekly · %">
        <LineTrend data={engagementTrend} series={[{ key: "TikTok", color: CHART.rose }, { key: "Instagram", color: CHART.plum }, { key: "Facebook", color: CHART.teal }]} />
      </ChartCard>
      <Panel padded={false}>
        <PanelHeader title="Platform breakdown" subtitle="All connected channels" className="p-4" />
        <div className="overflow-x-auto px-4 pb-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {["Platform", "Followers", "Reach", "Engagement", "Clicks", "Leads"].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {platformStats.filter((p) => p.connected).map((p) => (
                <tr key={p.platform} className="border-b border-border/70 last:border-0 hover:bg-surface-2">
                  <td className="px-3 py-3 font-medium text-ink">{p.platform}</td>
                  <td className="px-3 py-3 font-mono text-ink-muted tnum">{formatNumber(p.followers, true)}</td>
                  <td className="px-3 py-3 font-mono text-ink-muted tnum">{formatNumber(p.reach, true)}</td>
                  <td className="px-3 py-3 font-mono text-ink-muted tnum">{p.engagement}%</td>
                  <td className="px-3 py-3 font-mono text-ink-muted tnum">{formatNumber(p.clicks, true)}</td>
                  <td className="px-3 py-3 font-mono font-semibold text-rose tnum">{formatNumber(p.leads)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* --------------------------- Content calendar ------------------------------- */

function ContentCalendarTab() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Content calendar" />
      <Panel>
      <PanelHeader title="Content calendar" subtitle="This week · scheduled & pending posts" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-7">
        {contentCalendar.map((day) => (
          <div key={day.day} className="rounded-xl border border-border bg-surface-2 p-3">
            <p className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{day.day}</p>
            <div className="space-y-2">
              {day.posts.length === 0 ? (
                <p className="py-3 text-center text-xxs text-ink-faint">No posts</p>
              ) : (
                day.posts.map((post) => (
                  <div key={post.title} className="rounded-lg border border-border bg-surface p-2">
                    <p className="text-xs font-medium text-ink">{post.title}</p>
                    <p className="mt-0.5 text-xxs text-ink-faint">{post.platform} · {post.time}</p>
                    <StatusBadge tone={marketingStatusTone[post.status] ?? "neutral"} dot={false} className="mt-1.5">{post.status}</StatusBadge>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </Panel>
    </div>
  );
}

/* -------------------------------- Social posting ---------------------------- */

const draftCols: Column<SocialDraft>[] = [
  { key: "id", header: "Draft", primary: true, cell: (d) => <span className="font-mono text-xs font-semibold text-ink">{d.id}</span> },
  { key: "title", header: "Post", cell: (d) => <span className="text-ink">{d.title}</span> },
  { key: "platform", header: "Platform", cell: (d) => <StatusBadge tone="neutral" dot={false}>{d.platform}</StatusBadge> },
  { key: "type", header: "Type", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{d.type}</span> },
  { key: "scheduled", header: "Scheduled", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{d.scheduledFor}</span> },
  { key: "status", header: "Status", cell: (d) => <StatusBadge tone={socialDraftStatusTone[d.status]}>{d.status}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: (d) => (d.status === "Awaiting Approval" ? <Button size="sm" variant="primary">Review</Button> : <Button size="sm" variant="secondary">Edit</Button>) },
];

function SocialPostingTab() {
  const { filters } = useFilters();
  // Global geo/service/date narrow the drafts; platform + approval status are
  // marketing-specific axes handled locally.
  const localDefs: LocalFilterDef[] = [
    { key: "platform", label: "Platform", options: SOCIAL_PLATFORMS },
    { key: "status", label: "Approval status", options: SOCIAL_DRAFT_STATUSES },
  ];
  const lf = useLocalFilters(localDefs);
  const rows = applyGlobalFilters(socialDrafts, filters).filter((d) =>
    matchesLocal(d, lf.values, (row, key) => (key === "platform" ? row.platform : row.status)),
  );

  return (
    <Panel padded={false}>
      <PanelHeader title="Social posting" subtitle="Draft posts & channel selection — nothing posts without approval" className="p-4" action={<StatusBadge tone="rose">{rows.filter((d) => d.status === "Awaiting Approval").length} awaiting approval</StatusBadge>} />
      <div className="border-b border-border px-4 pb-3">
        <LocalFilterBar defs={localDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
      </div>
      <div className="px-4 pb-4 pt-4">
        <DataTable columns={draftCols} rows={rows} rowKey={(d) => d.id} empty={noMatch} onRowLabel={(d) => <StatusBadge tone={socialDraftStatusTone[d.status]}>{d.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ---------------------------------- Campaigns ------------------------------- */

const campaignCols: Column<Campaign>[] = [
  { key: "id", header: "Campaign", primary: true, cell: (c) => <span className="font-mono text-xs font-semibold text-ink">{c.id}</span> },
  { key: "name", header: "Name", cell: (c) => <span className="whitespace-nowrap font-medium text-ink">{c.name}</span> },
  { key: "channel", header: "Channel", cell: (c) => <span className="whitespace-nowrap text-xs text-ink-muted">{c.channel}</span> },
  { key: "status", header: "Status", cell: (c) => <StatusBadge tone={campaignStatusTone[c.status]}>{c.status}</StatusBadge> },
  { key: "spend", header: "Spend", align: "right", cell: (c) => <span className="font-mono text-sm text-ink tnum">{formatCurrency(c.spend)}</span> },
  { key: "reach", header: "Reach", align: "right", cell: (c) => <span className="font-mono text-xs text-ink-muted tnum">{formatNumber(c.reach, true)}</span> },
  { key: "leads", header: "Leads", align: "right", cell: (c) => <span className="font-mono text-sm font-semibold text-rose tnum">{c.leads}</span> },
  { key: "roas", header: "ROAS", align: "right", cell: (c) => <span className="font-mono text-xs text-ink-muted tnum">{c.roas}</span> },
];

function CampaignsTab() {
  const { filters } = useFilters();
  const localDefs: LocalFilterDef[] = [{ key: "status", label: "Campaign status", options: CAMPAIGN_STATUSES }];
  const lf = useLocalFilters(localDefs);
  // `channel` on a campaign is a display grouping ("Instagram + TikTok"), not the
  // global Channel dimension — exclude it from global channel matching. Geo/service/
  // date still apply. Campaign status is filtered locally.
  const rows = applyGlobalFilters(campaigns, { ...filters, channel: "" }).filter((c) =>
    matchesLocal(c, lf.values, (row) => row.status),
  );

  return (
    <Panel padded={false}>
      <PanelHeader title="Campaigns" subtitle="Channel, spend and performance" className="p-4" action={<StatusBadge tone="success">{rows.filter((c) => c.status === "Active").length} active</StatusBadge>} />
      <div className="border-b border-border px-4 pb-3">
        <LocalFilterBar defs={localDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
      </div>
      <div className="px-4 pb-4 pt-4">
        <DataTable columns={campaignCols} rows={rows} rowKey={(c) => c.id} empty={noMatch} onRowLabel={(c) => <StatusBadge tone={campaignStatusTone[c.status]}>{c.status}</StatusBadge>} />
      </div>
      <p className="flex items-center gap-1.5 border-t border-border px-4 py-3 text-xxs text-ink-faint"><Megaphone className="h-3 w-3" /> Connect an ad account to sync live spend & performance.</p>
    </Panel>
  );
}

/* -------------------------------- Approvals --------------------------------- */

function ApprovalQueueTab() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Marketing approvals" />
      <div className="grid gap-3 md:grid-cols-2">
      {marketingApprovals.map((m) => (
        <Panel key={m.id} className="flex flex-col">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{m.platform} · {m.assetType}</p>
              <p className="mt-1 text-sm text-ink">{m.caption}</p>
            </div>
            <StatusBadge tone={marketingStatusTone[m.status] ?? "neutral"}>{m.status}</StatusBadge>
          </div>
          <div className="mt-3 flex h-24 items-center justify-center rounded-xl border border-border bg-gradient-to-br from-rose/8 to-[rgb(var(--c-plum)/0.06)] text-xxs text-ink-faint">{m.assetType} preview</div>
          <p className="mt-2 text-xxs text-ink-faint">By {m.createdBy} · scheduled {new Date(m.scheduledFor).toLocaleDateString("en-AE", { day: "numeric", month: "short" })}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button>
            <Button size="sm" variant="secondary"><Pencil className="h-3.5 w-3.5" /> Request changes</Button>
            <Button size="sm" variant="ghost"><CalendarClock className="h-3.5 w-3.5" /> Schedule</Button>
            <Button size="sm" variant="danger"><X className="h-3.5 w-3.5" /> Reject</Button>
          </div>
        </Panel>
      ))}
      </div>
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
    <Panel>
      <PanelHeader title="Influencer & UGC outreach" subtitle="Creator shortlist — outreach drafted, not sent" />
      {rows.length === 0 ? (
        noMatch
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((c) => (
            <li key={c.name} className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-rose/12 text-rose"><Users className="h-4 w-4" /></span>
                <div>
                  <p className="text-sm font-medium text-ink">{c.name}</p>
                  <p className="text-xxs text-ink-faint">{c.followers} · {c.niche} · {c.city}</p>
                </div>
              </div>
              <StatusBadge tone={c.status === "Shortlisted" ? "info" : "warning"}>{c.status}</StatusBadge>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/* -------------------------------- PR & outreach ----------------------------- */

function PrOutreachTab() {
  const { filters } = useFilters();
  const localDefs: LocalFilterDef[] = [{ key: "status", label: "Draft status", options: PR_STATUSES }];
  const lf = useLocalFilters(localDefs);
  const rows: PrItem[] = applyGlobalFilters(prItems, filters).filter((p) =>
    matchesLocal(p, lf.values, (row) => row.status),
  );

  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="PR & outreach drafts" subtitle="Drafted by the agent — nothing sends without approval" className="p-4" action={<StatusBadge tone="warning">{rows.length} drafts · 0 sent</StatusBadge>} />
        <div className="border-b border-border px-4 pb-3">
          <LocalFilterBar defs={localDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
        </div>
        {rows.length === 0 ? (
          <div className="px-4 py-4">{noMatch}</div>
        ) : (
          <ul className="divide-y divide-border px-4 pb-2">
            {rows.map((p) => (
              <li key={`${p.outlet}-${p.topic}`} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{p.outlet}</p>
                  <p className="text-xxs text-ink-faint">{p.type} · {p.topic}</p>
                </div>
                <StatusBadge tone={p.status === "Ready to Send" ? "success" : p.status === "Held" ? "warning" : "neutral"}>{p.status}</StatusBadge>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel>
        <EmptyState icon={Mail} title="Apollo not connected" description="Outreach sequences are drafted by the agent and held here. Connect Apollo to enable sending after approval." action={<Button variant="outline" size="sm">Connect Apollo</Button>} />
      </Panel>
    </div>
  );
}

/* -------------------------------- UTM tracking ------------------------------ */

function UtmTrackingTab() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="UTM tracking" />
      <Panel padded={false}>
      <PanelHeader title="Campaign links & UTM" subtitle="Tracked links across channels" className="p-4" />
      <div className="overflow-x-auto px-4 pb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              {["Campaign", "Source", "UTM", "Clicks", "Leads"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {campaignLinks.map((c) => (
              <tr key={c.name} className="border-b border-border/70 last:border-0 hover:bg-surface-2">
                <td className="px-3 py-3 font-medium text-ink">{c.name}</td>
                <td className="px-3 py-3 text-ink-muted">{c.source}</td>
                <td className="px-3 py-3 font-mono text-xs text-ink-faint">{c.utm}</td>
                <td className="px-3 py-3 font-mono text-ink-muted tnum">{formatNumber(c.clicks)}</td>
                <td className="px-3 py-3 font-mono font-semibold text-rose tnum">{formatNumber(c.leads)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Marketing subsection by slug (see lib/dashboard/sections.ts). */
export function MarketingSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "overview": return <SocialOverviewTab />;
    case "platform-analytics": return <PlatformAnalyticsTab />;
    case "content-calendar": return <ContentCalendarTab />;
    case "creative-studio": return <CreativeStudio />;
    case "social-posting": return <SocialPostingTab />;
    case "campaigns": return <CampaignsTab />;
    case "approvals": return <ApprovalQueueTab />;
    case "influencer-ugc": return <InfluencerTab />;
    case "pr-outreach": return <PrOutreachTab />;
    case "utm-tracking": return <UtmTrackingTab />;
    default: return <SocialOverviewTab />;
  }
}
