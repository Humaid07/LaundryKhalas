import { Check, X, Clock, Pencil, ArrowUpRight, Activity as ActivityIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCurrency, formatNumber, formatRelativeTime } from "@/lib/dashboard/formatters";
import { agentStatusTone, riskTone, connectionTone, reportStatusTone } from "@/lib/dashboard/status-maps";
import { toneDot, toneText } from "./ui/tones";
import type {
  Approval,
  ActivityEvent,
  ConnectedApp,
  PlatformStat,
  ReportCardData,
  SeoAgent,
  CostLine,
  Tone,
} from "@/lib/dashboard/types";
import { Panel, StatusBadge, Eyebrow, DeltaChip } from "./ui/primitives";
import { Button } from "./ui/Button";

/* ------------------------------ Agent status card --------------------------- */

export function AgentStatusCard({ agent }: { agent: SeoAgent }) {
  return (
    <div className="group flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Eyebrow>{agent.category}</Eyebrow>
          <h4 className="mt-1 text-sm font-semibold leading-snug text-ink">{agent.name}</h4>
        </div>
        <StatusBadge tone={agentStatusTone[agent.status]}>{agent.status}</StatusBadge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Meta label="Last run" value={agent.lastRun === "—" ? "—" : formatRelativeTime(agent.lastRun)} />
        <Meta label="Next run" value={agent.nextRun === "—" ? "Paused" : formatRelativeTime(agent.nextRun)} />
        <Meta label="Outputs" value={formatNumber(agent.outputs)} mono />
        <Meta
          label="Open issues"
          value={String(agent.openIssues)}
          mono
          tone={agent.openIssues > 0 ? "text-warning" : undefined}
        />
      </div>
      {agent.approvalRequired && (
        <div className="mt-4 flex items-center gap-1.5 rounded-lg bg-rose/8 px-2.5 py-1.5 text-xxs font-semibold text-rose">
          <Clock className="h-3.5 w-3.5" /> Approval required
        </div>
      )}
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <p className={cn("mt-0.5 truncate font-medium text-ink", mono && "font-mono tnum", tone)}>{value}</p>
    </div>
  );
}

/* ------------------------------- Approval card ------------------------------ */

export function ApprovalCard({ approval, compact = false }: { approval: Approval; compact?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{approval.type}</span>
            <StatusBadge tone={riskTone[approval.risk]} dot={false}>
              {approval.risk} risk
            </StatusBadge>
          </div>
          <p className="mt-1.5 text-sm text-ink">{approval.summary}</p>
          <p className="mt-1 text-xxs text-ink-faint">
            {approval.requestedBy} · {approval.channel} · {formatRelativeTime(approval.createdAt)}
          </p>
        </div>
      </div>
      {!compact && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="primary">
            <Check className="h-3.5 w-3.5" /> Approve
          </Button>
          <Button size="sm" variant="secondary">
            <Pencil className="h-3.5 w-3.5" /> Edit
          </Button>
          <Button size="sm" variant="danger">
            <X className="h-3.5 w-3.5" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}

/* ------------------------------ Activity timeline --------------------------- */

type TimelineEvent = Pick<ActivityEvent, "id" | "title" | "detail" | "time" | "tone"> & {
  actor?: string;
};

export function ActivityTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative space-y-4 before:absolute before:left-[5px] before:top-1 before:h-[calc(100%-0.5rem)] before:w-px before:bg-border">
      {events.map((e) => (
        <li key={e.id} className="relative flex gap-3 pl-5">
          <span className={cn("absolute left-0 top-1 h-2.5 w-2.5 rounded-full ring-4 ring-surface", toneDot[e.tone])} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink">{e.title}</p>
            <p className="truncate text-xs text-ink-muted">{e.detail}</p>
            <p className="mt-0.5 text-xxs text-ink-faint">
              {e.actor ? `${e.actor} · ` : ""}
              {formatRelativeTime(e.time)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/* -------------------------------- Report card ------------------------------- */

export function ReportCard({ report }: { report: ReportCardData }) {
  return (
    <Panel className="flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-sm font-semibold text-ink">{report.name}</h4>
          <p className="mt-0.5 text-xxs text-ink-faint">
            {report.audience} · {report.frequency}
          </p>
        </div>
        <StatusBadge tone={reportStatusTone[report.status]}>{report.status}</StatusBadge>
      </div>
      <p className="mt-3 flex-1 text-xs leading-relaxed text-ink-muted">{report.summary}</p>
      <div className="mt-4 flex items-center justify-between">
        <span className="text-xxs text-ink-faint">Updated {formatRelativeTime(report.lastGenerated)}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost">
            Export
          </Button>
          <Button size="sm" variant="primary">
            View <ArrowUpRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/* ---------------------------- Platform metric card -------------------------- */

export function PlatformMetricCard({ platform }: { platform: PlatformStat }) {
  if (!platform.connected) {
    return (
      <div className="flex flex-col justify-between rounded-2xl border border-dashed border-border bg-surface-2 p-4">
        <div className="flex items-center justify-between">
          <span className="font-display text-sm font-semibold text-ink">{platform.platform}</span>
          <StatusBadge tone="neutral" dot={false}>
            Not connected
          </StatusBadge>
        </div>
        <Button size="sm" variant="outline" className="mt-4 w-full justify-center">
          Connect
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-300 hover:-translate-y-0.5 hover:shadow-raised">
      <div className="flex items-center justify-between">
        <span className="font-display text-sm font-semibold text-ink">{platform.platform}</span>
        <DeltaChip delta={platform.delta} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-y-3">
        <PlatformMetric label="Reach" value={formatNumber(platform.reach, true)} />
        <PlatformMetric label="Engagement" value={`${platform.engagement}%`} />
        <PlatformMetric label="Clicks" value={formatNumber(platform.clicks, true)} />
        <PlatformMetric label="Leads" value={formatNumber(platform.leads)} accent />
      </div>
    </div>
  );
}

function PlatformMetric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <p className={cn("mt-0.5 font-mono text-sm font-semibold tnum", accent ? "text-rose" : "text-ink")}>{value}</p>
    </div>
  );
}

/* -------------------------- Finance breakdown card -------------------------- */

export function FinanceBreakdownCard({ lines }: { lines: CostLine[] }) {
  const max = Math.max(...lines.map((l) => l.pctOfCost));
  return (
    <div className="space-y-3">
      {lines.map((l) => (
        <div key={l.category}>
          <div className="flex items-center justify-between gap-3 text-sm">
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full", toneDot[l.tone])} />
              <span className="font-medium text-ink">{l.category}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-ink tnum">{formatCurrency(l.amount, "AED", true)}</span>
              <span className="w-12 text-right font-mono text-xs text-ink-muted tnum">{l.pctOfCost.toFixed(1)}%</span>
            </div>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink/6">
            <div
              className={cn("h-full rounded-full", toneDot[l.tone])}
              style={{ width: `${(l.pctOfCost / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ----------------------------- Connected app row ---------------------------- */

export function ConnectedAppRow({ app }: { app: ConnectedApp }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface font-display text-sm font-semibold text-ink-muted ring-1 ring-border">
          {app.name.slice(0, 1)}
        </span>
        <div>
          <p className="text-sm font-medium text-ink">{app.name}</p>
          <p className="text-xxs text-ink-faint">{app.category}</p>
        </div>
      </div>
      <StatusBadge tone={connectionTone[app.status]}>{app.status}</StatusBadge>
    </div>
  );
}

/* -------------------------------- Mini metric ------------------------------- */

export function MiniMetric({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: number;
  tone?: Tone;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3">
      <div className="flex items-center gap-2">
        <ActivityIcon className={cn("h-3.5 w-3.5", toneText[tone])} />
        <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{label}</p>
      </div>
      <div className="mt-1.5 flex items-end justify-between">
        <span className="font-mono text-lg font-semibold text-ink tnum">{value}</span>
        {typeof delta === "number" && <DeltaChip delta={delta} />}
      </div>
    </div>
  );
}
