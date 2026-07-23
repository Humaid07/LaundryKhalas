"use client";

import {
  ReceiptText, ShieldCheck, Check, X, MessageSquare, StickyNote, MapPin, UserCog,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  approvalTone, refundIsActionable, type RefundAdjustment,
} from "@/lib/dashboard/finance-compliance-data";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";

const ACTIONS = (r: RefundAdjustment): MenuItem[] => {
  const actionable = refundIsActionable(r.approval);
  return [
    { label: "Approve", icon: Check, approval: true, disabled: !actionable },
    { label: "Decline", icon: X, tone: "danger", approval: true, disabled: !actionable },
    { label: "Request more info", icon: MessageSquare, disabled: !actionable },
    { label: "Add note", icon: StickyNote },
  ];
};

export function RefundDetailPage({ refund, backHref }: { refund: RefundAdjustment; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Refunds & Adjustments"
      eyebrow={refund.type === "Refund" ? "Refund request" : "Adjustment"}
      title={<span className="font-mono">{refund.id}</span>}
      status={
        <>
          <StatusBadge tone={approvalTone[refund.approval]} dot={false}>{refund.approval}</StatusBadge>
          <StatusBadge tone={refund.type === "Refund" ? "plum" : "neutral"} dot={false}>{refund.type}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(refund)} />}
    >
      <DetailColumns
        main={
          <DetailSectionCard title="Request" icon={ReceiptText}>
            <FieldGrid>
              <Field label="Reference" value={refund.id} mono />
              <Field label="Type" value={refund.type} />
              <Field label="Order" value={refund.orderRef} mono />
              <Field label="Amount" value={formatCurrency(refund.amount)} mono />
              <Field label="Reason" value={refund.reason} />
              <Field label="Requested" value={formatRelativeTime(refund.createdAt)} />
              <Field
                label="City"
                value={<span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{refund.city}</span>}
              />
            </FieldGrid>
          </DetailSectionCard>
        }
        sidebar={
          <>
            <DetailSectionCard title="Approval" icon={UserCog} bodyClassName="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-ink-muted">Status</span>
                <Chip tone={approvalTone[refund.approval]}>{refund.approval}</Chip>
              </div>
              <FieldGrid cols={2}>
                <Field label="Amount" value={formatCurrency(refund.amount)} mono />
                <Field label="Reviewer" value={refund.reviewer} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Approval-gated" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Every refund and adjustment requires human sign-off before any money moves. Approve / decline are logged and cannot be run autonomously.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
