"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { OrderTimeline } from "@/components/orders/OrderTimeline";
import { formatCurrency, formatDateTime, shortId } from "@/lib/formatters";

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const orderQ = useQuery({ queryKey: ["order", id], queryFn: () => api.getOrder(id) });
  const eventsQ = useQuery({ queryKey: ["order-events", id], queryFn: () => api.listOrderEvents(id) });
  const marketsQ = useQuery({ queryKey: ["markets"], queryFn: api.listMarkets });
  const logsQ = useQuery({
    queryKey: ["ai-action-logs", "order", id],
    queryFn: () => api.listAiActionLogs({ order_id: id }),
  });

  const linkedConversationId = useMemo(
    () => (logsQ.data ?? []).find((l) => l.conversation_id)?.conversation_id ?? null,
    [logsQ.data]
  );

  const refetchAll = () => {
    orderQ.refetch();
    eventsQ.refetch();
    logsQ.refetch();
  };

  if (orderQ.isLoading) return <LoadingState label="Loading order…" />;
  if (orderQ.error || !orderQ.data) {
    return (
      <ErrorState
        message={orderQ.error instanceof Error ? orderQ.error.message : "Order not found."}
        onRetry={() => orderQ.refetch()}
      />
    );
  }

  const order = orderQ.data;
  const marketCode = marketsQ.data?.find((m) => m.id === order.market_id)?.code ?? order.market_id.slice(0, 8);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => router.push("/admin/orders")}
          className="flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to orders
        </button>
        <Button variant="secondary" size="sm" onClick={refetchAll}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">Order {shortId(order.id)}</h2>
              <StatusBadge status={order.status} />
            </CardHeader>
            <CardBody className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              <Field label="Market" value={marketCode} />
              <Field label="Customer" value={`Customer ${shortId(order.customer_id)}`} />
              <Field label="Service type" value={order.service_type.replace(/_/g, " ")} />
              <Field label="Estimated total" value={formatCurrency(order.estimated_total)} />
              <Field label="Payment status" value={<StatusBadge status={order.payment_status} />} />
              <Field label="Source channel" value={<span className="capitalize">{order.source_channel}</span>} />
              <Field
                label="Facility"
                value={order.facility_id ? shortId(order.facility_id) : "Not yet assigned"}
              />
              <Field
                label="Pickup window"
                value={
                  order.pickup_window_start
                    ? `${formatDateTime(order.pickup_window_start)} – ${formatDateTime(order.pickup_window_end)}`
                    : "-"
                }
              />
              <Field
                label="Delivery window"
                value={
                  order.delivery_window_start
                    ? `${formatDateTime(order.delivery_window_start)} – ${formatDateTime(order.delivery_window_end)}`
                    : "Not yet scheduled"
                }
              />
              <Field label="Created" value={formatDateTime(order.created_at)} />
            </CardBody>
          </Card>

          <OrderTimeline events={eventsQ.data ?? []} />
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-ink">Linked conversation</h2>
            </CardHeader>
            <CardBody>
              {linkedConversationId ? (
                <Link
                  href={`/admin/conversations/${linkedConversationId}`}
                  className="text-sm font-medium text-brand hover:text-brand-hover"
                >
                  Conversation {shortId(linkedConversationId)}
                </Link>
              ) : (
                <p className="text-sm text-ink-muted">No linked conversation found.</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-ink">AI action logs</h2>
            </CardHeader>
            <CardBody className="p-0">
              {(logsQ.data ?? []).length === 0 ? (
                <p className="px-5 py-4 text-sm text-ink-muted">No AI actions logged for this order.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {(logsQ.data ?? []).slice(0, 8).map((log) => (
                    <li key={log.id} className="px-5 py-2.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink">{log.tool_name ?? log.action_type}</span>
                        <span className={log.success ? "text-success" : "text-danger"}>
                          {log.success ? "ok" : "failed"}
                        </span>
                      </div>
                      <span className="text-ink-faint">{formatDateTime(log.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
            <div className="border-t border-border px-5 py-2.5">
              <Link
                href={`/admin/ai-logs?order_id=${order.id}`}
                className="text-xs font-medium text-brand hover:text-brand-hover"
              >
                View all in AI Logs
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="mt-0.5 font-medium text-ink">{value}</p>
    </div>
  );
}
