"use client";

import { Bot, Gauge, ScrollText, RotateCw, Pause, Play, Settings2, UserPlus, CirclePlus, Activity, ShieldCheck } from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import { agentStatusToneD, type AgentHealth } from "@/lib/dashboard/dev-automation-data";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

/** Detail-page actions for an agent. Retry & pause/resume are approval-gated
 * (RULE 13); nothing performs a live action in mock mode. */
const ACTIONS = (a: AgentHealth): MenuItem[] => [
  { label: "View logs", icon: ScrollText },
  { label: "Run health check", icon: Activity },
  { label: "Retry last job", icon: RotateCw, approval: true, disabled: a.issues === 0 },
  { label: "Pause agent", icon: Pause, approval: true, disabled: a.status === "Paused" },
  { label: "Resume agent", icon: Play, approval: true, disabled: a.status !== "Paused" },
  { label: "View config", icon: Settings2 },
  { label: "Assign owner", icon: UserPlus },
  { label: "Create issue", icon: CirclePlus },
];

export function AgentDetailPage({ agent, backHref }: { agent: AgentHealth; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Agent health"
      eyebrow={agent.category}
      title={agent.name}
      status={
        <>
          <StatusBadge tone={agentStatusToneD[agent.status]} dot={false}>{agent.status}</StatusBadge>
          <StatusBadge tone="neutral" dot={false}>{agent.mode}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(agent)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Agent" icon={Bot}>
              <FieldGrid>
                <Field label="Name" value={agent.name} />
                <Field label="Category" value={agent.category} />
                <Field label="Status" value={<Chip tone={agentStatusToneD[agent.status]}>{agent.status}</Chip>} />
                <Field label="Mode" value={<Chip tone="neutral">{agent.mode}</Chip>} />
                <Field label="Last run" value={fmtTime(agent.lastRun)} />
                <Field label="Next run" value={fmtTime(agent.nextRun)} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Performance" icon={Gauge}>
              <FieldGrid>
                <Field label="Success rate" value={agent.successRate ? `${agent.successRate}%` : "—"} />
                <Field label="Avg latency" value={agent.avgLatency} />
                <Field label="Cost today" value={agent.costToday ? formatCurrency(agent.costToday) : "—"} />
                <Field label="Open issues" value={<span className={agent.issues > 0 ? "text-warning" : undefined}>{agent.issues}</span>} />
              </FieldGrid>
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Ownership" icon={UserPlus}>
              <FieldGrid cols={2}>
                <Field label="Owner" value={agent.owner} />
                <Field label="Mode" value={<Chip tone="neutral">{agent.mode}</Chip>} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Safety" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Approval-gated agent — customer-facing output requires human sign-off in MVP. No secrets, tokens or raw environment values are shown.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
