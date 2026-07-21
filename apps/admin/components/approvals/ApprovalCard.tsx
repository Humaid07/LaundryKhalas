import Link from "next/link";
import { Check, X } from "lucide-react";
import { Card, CardBody } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { JsonViewer } from "@/components/ui/json-viewer";
import { formatDateTime, shortId } from "@/lib/formatters";
import type { HumanApproval } from "@/lib/types";

export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  isDeciding,
}: {
  approval: HumanApproval;
  onApprove: () => void;
  onReject: () => void;
  isDeciding: boolean;
}) {
  const isPending = approval.status === "pending";

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-ink">{approval.action_type}</p>
            <p className="text-xs text-ink-muted">Requested by {approval.requested_by_agent}</p>
          </div>
          <StatusBadge status={approval.status} />
        </div>

        {approval.reason && <p className="text-xs text-ink-muted">Reason: {approval.reason}</p>}

        {approval.proposed_payload_json?.text && (
          <div className="rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink">
            {approval.proposed_payload_json.text}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
          {approval.conversation_id && (
            <Link
              href={`/admin/conversations/${approval.conversation_id}`}
              className="font-medium text-brand hover:text-brand-hover"
            >
              Conversation {shortId(approval.conversation_id)}
            </Link>
          )}
          {approval.order_id && (
            <Link
              href={`/admin/orders/${approval.order_id}`}
              className="font-medium text-brand hover:text-brand-hover"
            >
              Order {shortId(approval.order_id)}
            </Link>
          )}
          <span>{formatDateTime(approval.created_at)}</span>
        </div>

        {!isPending && (
          <div className="text-xs text-ink-muted">
            {approval.status === "approved" ? "Approved" : "Rejected"} by{" "}
            {approval.approved_by ?? approval.rejected_by ?? "-"}
            {approval.decision_note && <> &mdash; &ldquo;{approval.decision_note}&rdquo;</>}
          </div>
        )}

        <JsonViewer data={approval.proposed_payload_json} label="Full proposed payload" />

        {isPending && (
          <div className="flex justify-end gap-2 border-t border-border pt-3">
            <button
              onClick={onReject}
              disabled={isDeciding}
              className="flex items-center gap-1.5 rounded-lg border border-border-strong bg-white px-3 py-1.5 text-xs font-medium text-ink hover:bg-neutral-soft disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5" />
              Reject
            </button>
            <button
              onClick={onApprove}
              disabled={isDeciding}
              className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-hover disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" />
              Approve Reply
            </button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
