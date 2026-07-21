import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { StatusBadge, BooleanBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCurrency, formatRelativeTime, shortId } from "@/lib/formatters";
import type { AIActionLog, Conversation, HumanApproval, Order } from "@/lib/types";

export function ConversationContextPanel({
  conversation,
  marketCode,
  order,
  pendingApprovals,
  recentLogs,
  onApprove,
  onReject,
  isDeciding,
}: {
  conversation: Conversation;
  marketCode: string;
  order: Order | null;
  pendingApprovals: HumanApproval[];
  recentLogs: AIActionLog[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  isDeciding: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-ink">Conversation</h2>
        </CardHeader>
        <CardBody className="space-y-2.5 text-sm">
          <Row label="Customer" value={`Customer ${shortId(conversation.customer_id)}`} />
          <Row label="Market" value={marketCode} />
          <Row label="Channel" value={<span className="capitalize">{conversation.channel}</span>} />
          <Row label="Status" value={<StatusBadge status={conversation.status} />} />
          <Row
            label="Manual takeover"
            value={
              conversation.manual_takeover ? (
                <BooleanBadge value trueLabel="Active" />
              ) : (
                <span className="text-ink-muted">Off</span>
              )
            }
          />
          <Row label="Updated" value={formatRelativeTime(conversation.updated_at)} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-ink">Related order</h2>
        </CardHeader>
        <CardBody>
          {order ? (
            <Link href={`/admin/orders/${order.id}`} className="block space-y-2.5 text-sm">
              <Row label="Order" value={<span className="font-medium text-brand">{shortId(order.id)}</span>} />
              <Row label="Status" value={<StatusBadge status={order.status} />} />
              <Row label="Service" value={order.service_type.replace(/_/g, " ")} />
              <Row label="Total" value={formatCurrency(order.estimated_total)} />
            </Link>
          ) : (
            <p className="text-sm text-ink-muted">No order created yet for this conversation.</p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-ink">Pending approvals</h2>
        </CardHeader>
        <CardBody className="p-0">
          {pendingApprovals.length === 0 ? (
            <div className="px-5 py-4">
              <p className="text-sm text-ink-muted">Nothing awaiting a decision.</p>
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {pendingApprovals.map((a) => (
                <li key={a.id} className="space-y-2 px-5 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-ink">{a.action_type}</span>
                    <StatusBadge status={a.status} />
                  </div>
                  {a.proposed_payload_json?.text && (
                    <p className="text-xs text-ink-muted">{a.proposed_payload_json.text}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => onReject(a.id)}
                      disabled={isDeciding}
                      className="rounded-lg border border-border-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-neutral-soft disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => onApprove(a.id)}
                      disabled={isDeciding}
                      className="rounded-lg bg-brand px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-hover disabled:opacity-50"
                    >
                      Approve
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Latest AI action logs</h2>
          <Link
            href={`/admin/ai-logs?conversation_id=${conversation.id}`}
            className="text-xs font-medium text-brand hover:text-brand-hover"
          >
            View all
          </Link>
        </CardHeader>
        <CardBody className="p-0">
          {recentLogs.length === 0 ? (
            <EmptyState title="No actions logged yet" />
          ) : (
            <ul className="divide-y divide-border">
              {recentLogs.slice(0, 5).map((log) => (
                <li key={log.id} className="px-5 py-2.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink">
                      {log.tool_name ?? log.action_type}
                    </span>
                    <span className={log.success ? "text-success" : "text-danger"}>
                      {log.success ? "ok" : "failed"}
                    </span>
                  </div>
                  <span className="text-ink-faint">{formatRelativeTime(log.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <div className="flex items-start gap-2 rounded-2xl border border-info/20 bg-info-soft px-4 py-3 text-xs text-info-text">
        <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <p>
          Privacy firewall active: customer phone, email, and full address are never sent to the
          LLM or shown in this interface - only area/city and this conversation&apos;s messages are used.
        </p>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-ink-muted">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}
