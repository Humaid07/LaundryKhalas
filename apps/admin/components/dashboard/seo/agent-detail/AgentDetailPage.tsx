import {
  Bot, Gauge, CalendarClock, ShieldCheck, ListChecks, Play, Pause,
  History, SlidersHorizontal, BadgeCheck, AlertTriangle,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, EmptyState, type MenuItem,
} from "@/components/dashboard/minimal";
import { agentStatusTone, priorityTone } from "@/lib/dashboard/status-maps";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { seoTasksForAgent } from "@/lib/dashboard/seo-data";
import type { SeoAgent } from "@/lib/dashboard/types";

/**
 * Full-page SEO agent detail — the ONLY place an agent's actions live. Main-page
 * fleet cards are light previews that click through here (progressive disclosure).
 * All actions are mock/approval-gated; risky ones carry `approval: true` (RULE 13).
 */
const ACTIONS = (a: SeoAgent): MenuItem[] => [
  { label: "Run agent now", icon: Play, approval: true },
  { label: a.status === "Paused" ? "Resume agent" : "Pause agent", icon: Pause },
  { label: "Approve pending output", icon: BadgeCheck, approval: true, disabled: !a.approvalRequired },
  { label: "View run history", icon: History },
  { label: "Configure schedule", icon: SlidersHorizontal },
];

const fmt = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

export function AgentDetailPage({ agent, backHref }: { agent: SeoAgent; backHref: string }) {
  const tasks = seoTasksForAgent(agent.name);
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Agent fleet"
      eyebrow="SEO agent"
      title={agent.name}
      status={
        <>
          <StatusBadge tone={agentStatusTone[agent.status]} dot={false}>{agent.status}</StatusBadge>
          {agent.approvalRequired && <StatusBadge tone="rose" dot={false}>Approval-gated</StatusBadge>}
        </>
      }
      actions={<ActionMenu items={ACTIONS(agent)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Agent" icon={Bot}>
              <FieldGrid>
                <Field label="Category" value={agent.category} />
                <Field label="Status" value={<Chip tone={agentStatusTone[agent.status]}>{agent.status}</Chip>} />
                <Field label="Last run" value={fmt(agent.lastRun)} />
                <Field label="Next run" value={agent.nextRun === "—" ? "—" : agent.nextRun} />
                <Field label="Outputs" value={String(agent.outputs)} />
                <Field label="Open issues" value={String(agent.openIssues)} />
              </FieldGrid>
            </DetailSectionCard>

            <DetailSectionCard title="Linked tasks" icon={ListChecks}>
              {tasks.length === 0 ? (
                <EmptyState icon={ListChecks} title="No open tasks" description="This agent has no tasks in the current backlog." />
              ) : (
                <ul className="divide-y divide-border/60">
                  {tasks.map((t) => (
                    <li key={t.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink">{t.task}</p>
                        <p className="mt-0.5 font-mono text-xxs text-ink-faint">{t.url}</p>
                        <p className="mt-1 text-xs text-ink-muted">{t.suggestedAction}</p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <Chip tone={priorityTone[t.priority]}>{t.priority}</Chip>
                        {t.approvalRequired && (
                          <span className="text-xxs font-semibold uppercase tracking-eyebrow text-warning">Approval</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Schedule" icon={CalendarClock}>
              <FieldGrid cols={2}>
                <Field label="Last run" value={fmt(agent.lastRun)} />
                <Field label="Next run" value={agent.nextRun === "—" ? "—" : agent.nextRun} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Health" icon={Gauge}>
              <FieldGrid cols={2}>
                <Field label="Outputs" value={String(agent.outputs)} />
                <Field
                  label="Open issues"
                  value={
                    agent.openIssues > 0 ? (
                      <span className="inline-flex items-center gap-1 text-warning">
                        <AlertTriangle className="h-3.5 w-3.5" />{agent.openIssues}
                      </span>
                    ) : "0"
                  }
                />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Governance" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                {agent.approvalRequired
                  ? "Outputs from this agent require human approval before they take effect. Nothing is published autonomously."
                  : "This agent is monitor-only. It surfaces findings but takes no autonomous action."}
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
