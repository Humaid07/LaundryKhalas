"use client";

import {
  LifeBuoy, Reply, MessagesSquare, ArrowUpRight, Link2, StickyNote, Check, Gauge, ShieldCheck,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import { ticketStatusTone, priorityTone } from "@/lib/dashboard/status-maps";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { Ticket } from "@/lib/dashboard/types";

const ACTIONS = (t: Ticket): MenuItem[] => [
  { label: "Respond", icon: Reply },
  { label: "Reassign", icon: MessagesSquare },
  { label: "Escalate to human", icon: ArrowUpRight, approval: true },
  { label: "View linked order", icon: Link2 },
  { label: "Add note", icon: StickyNote },
  { label: "Resolve ticket", icon: Check, disabled: t.status === "Resolved" },
];

export function TicketDetailPage({ ticket: t, backHref }: { ticket: Ticket; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Customer Facing"
      eyebrow="Support ticket"
      title={<span className="font-mono">{t.id}</span>}
      status={
        <>
          <StatusBadge tone={priorityTone[t.priority]} dot={false}>{t.priority}</StatusBadge>
          <StatusBadge tone={ticketStatusTone[t.status]} dot={false}>{t.status}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(t)} />}
    >
      <DetailColumns
        main={
          <DetailSectionCard title="Ticket" icon={LifeBuoy}>
            <FieldGrid>
              <Field label="Subject" value={t.subject} />
              <Field label="Category" value={t.category} />
              <Field label="Source" value={t.source} />
              <Field label="Assignee" value={t.assignee} />
              <Field label="City" value={t.city} />
              <Field label="Created" value={formatRelativeTime(t.createdAt)} />
            </FieldGrid>
          </DetailSectionCard>
        }
        sidebar={
          <>
            <DetailSectionCard title="SLA" icon={Gauge}>
              <div className="flex items-center justify-between">
                <span className="text-sm text-ink-muted">Time left</span>
                <StatusBadge tone={t.status === "Resolved" ? "neutral" : t.slaMinutesLeft < 30 ? "danger" : "warning"} dot={false}>
                  {t.status === "Resolved" ? "Closed" : `${t.slaMinutesLeft}m`}
                </StatusBadge>
              </div>
            </DetailSectionCard>
            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Outbound replies, escalations and refunds require human approval before they take effect. Nothing is sent live from this view.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
