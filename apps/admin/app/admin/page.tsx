"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody, CardHeader, StatTile } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge, BooleanBadge } from "@/components/ui/status-badge";
import { formatCurrency, formatRelativeTime, shortId } from "@/lib/formatters";

export default function OverviewPage() {
  const conversationsQ = useQuery({
    queryKey: ["conversations"],
    queryFn: api.listConversations,
  });
  const approvalsQ = useQuery({ queryKey: ["approvals"], queryFn: () => api.listApprovals() });
  const ordersQ = useQuery({ queryKey: ["orders"], queryFn: api.listOrders });
  const logsQ = useQuery({
    queryKey: ["ai-action-logs", "overview"],
    queryFn: () => api.listAiActionLogs({ limit: "500" }),
  });

  const isLoading =
    conversationsQ.isLoading || approvalsQ.isLoading || ordersQ.isLoading || logsQ.isLoading;
  const error = conversationsQ.error || approvalsQ.error || ordersQ.error || logsQ.error;

  const refetchAll = () => {
    conversationsQ.refetch();
    approvalsQ.refetch();
    ordersQ.refetch();
    logsQ.refetch();
  };

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Snapshot of the WhatsApp Operations Agent MVP - conversations, approvals, orders, and agent activity."
        actions={
          <Button variant="secondary" size="sm" onClick={refetchAll}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {isLoading && <LoadingState label="Loading overview…" />}
      {error && !isLoading && (
        <ErrorState message={(error as Error).message} onRetry={refetchAll} />
      )}

      {!isLoading && !error && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <StatTile label="Total conversations" value={conversationsQ.data?.length ?? 0} />
            <StatTile
              label="Open conversations"
              value={conversationsQ.data?.filter((c) => c.status === "open").length ?? 0}
            />
            <StatTile
              label="Manual takeover"
              value={conversationsQ.data?.filter((c) => c.manual_takeover).length ?? 0}
              hint="Agent auto-run disabled"
            />
            <StatTile
              label="Pending approvals"
              value={approvalsQ.data?.filter((a) => a.status === "pending").length ?? 0}
              hint="Awaiting admin decision"
            />
            <StatTile label="Orders created" value={ordersQ.data?.length ?? 0} />
            <StatTile
              label="Outbound messages sent"
              value={
                approvalsQ.data?.filter(
                  (a) => a.status === "approved" && a.action_type === "send_customer_reply"
                ).length ?? 0
              }
              hint="Approved replies sent to the customer"
            />
            <StatTile label="AI actions logged" value={logsQ.data?.length ?? 0} />
            <StatTile
              label="Failed agent actions"
              value={logsQ.data?.filter((l) => !l.success).length ?? 0}
            />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <RecentConversations conversations={conversationsQ.data ?? []} />
            <RecentApprovals approvals={approvalsQ.data ?? []} />
            <RecentOrders orders={ordersQ.data ?? []} />
          </div>
        </>
      )}
    </div>
  );
}

function RecentConversations({ conversations }: { conversations: import("@/lib/types").Conversation[] }) {
  const recent = [...conversations]
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    .slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Recent conversations</h2>
        <Link href="/admin/conversations" className="text-xs font-medium text-brand hover:text-brand-hover">
          View all
        </Link>
      </CardHeader>
      <CardBody className="p-0">
        {recent.length === 0 ? (
          <EmptyState title="No conversations yet" description="Send an inbound message to get started." />
        ) : (
          <ul className="divide-y divide-border">
            {recent.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/admin/conversations/${c.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-neutral-soft/60"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">Conversation {shortId(c.id)}</p>
                    <p className="text-xs text-ink-muted">{formatRelativeTime(c.updated_at)}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1.5">
                    {c.manual_takeover && <BooleanBadge value trueLabel="Manual" />}
                    <StatusBadge status={c.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function RecentApprovals({ approvals }: { approvals: import("@/lib/types").HumanApproval[] }) {
  const recent = [...approvals].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Recent approvals</h2>
        <Link href="/admin/approvals" className="text-xs font-medium text-brand hover:text-brand-hover">
          View all
        </Link>
      </CardHeader>
      <CardBody className="p-0">
        {recent.length === 0 ? (
          <EmptyState title="No approvals yet" description="Run the agent on a conversation to create one." />
        ) : (
          <ul className="divide-y divide-border">
            {recent.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{a.action_type}</p>
                  <p className="text-xs text-ink-muted">{formatRelativeTime(a.created_at)}</p>
                </div>
                <StatusBadge status={a.status} />
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function RecentOrders({ orders }: { orders: import("@/lib/types").Order[] }) {
  const recent = [...orders].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Recent orders</h2>
        <Link href="/admin/orders" className="text-xs font-medium text-brand hover:text-brand-hover">
          View all
        </Link>
      </CardHeader>
      <CardBody className="p-0">
        {recent.length === 0 ? (
          <EmptyState title="No orders yet" description="Orders appear once the agent completes the happy path." />
        ) : (
          <ul className="divide-y divide-border">
            {recent.map((o) => (
              <li key={o.id}>
                <Link
                  href={`/admin/orders/${o.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-neutral-soft/60"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">Order {shortId(o.id)}</p>
                    <p className="text-xs text-ink-muted">{formatCurrency(o.estimated_total)}</p>
                  </div>
                  <StatusBadge status={o.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
