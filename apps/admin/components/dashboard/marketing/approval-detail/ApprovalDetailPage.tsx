"use client";

import {
  ImageIcon, ShieldCheck, Check, PencilLine, CalendarClock, X, MessageSquare,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import type { MarketingApproval } from "@/lib/dashboard/types";
import { marketingStatusTone } from "@/lib/dashboard/status-maps";

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("en-AE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

const ACTIONS: MenuItem[] = [
  { label: "Approve & schedule", icon: Check, approval: true },
  { label: "Request changes", icon: PencilLine },
  { label: "Reschedule", icon: CalendarClock },
  { label: "Add note", icon: MessageSquare },
  { label: "Reject", icon: X, tone: "danger" },
];

export function ApprovalDetailPage({ approval, backHref }: { approval: MarketingApproval; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Approvals"
      eyebrow="Marketing approval"
      title={`${approval.platform} · ${approval.assetType}`}
      status={<StatusBadge tone={marketingStatusTone[approval.status] ?? "neutral"} dot={false}>{approval.status}</StatusBadge>}
      actions={<ActionMenu items={ACTIONS} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Draft" icon={ImageIcon}>
              <div className="mb-4 flex h-40 items-center justify-center rounded-xl border border-border bg-surface-2 text-xxs uppercase tracking-eyebrow text-ink-faint">
                {approval.assetType} preview
              </div>
              <FieldGrid>
                <Field label="Platform" value={approval.platform} />
                <Field label="Asset type" value={approval.assetType} />
                <Field label="Caption" value={approval.caption} />
                <Field label="Scheduled for" value={fmtDate(approval.scheduledFor)} />
              </FieldGrid>
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Origin" icon={ShieldCheck}>
              <FieldGrid cols={2}>
                <Field label="Created by" value={approval.createdBy} />
                <Field label="Status" value={approval.status} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Approval gate" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Agent-drafted content. Nothing publishes without a human sign-off — approve, request changes, or reject from the ActionMenu.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
