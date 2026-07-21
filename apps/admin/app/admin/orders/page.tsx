"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { DataTable, type Column } from "@/components/ui/data-table";
import { formatCurrency, formatDateTime, shortId } from "@/lib/formatters";
import type { Order } from "@/lib/types";
import Link from "next/link";

export default function OrdersPage() {
  const [status, setStatus] = useState("all");
  const [market, setMarket] = useState("all");
  const [serviceType, setServiceType] = useState("all");
  const [search, setSearch] = useState("");

  const ordersQ = useQuery({ queryKey: ["orders"], queryFn: api.listOrders });
  const marketsQ = useQuery({ queryKey: ["markets"], queryFn: api.listMarkets });

  const marketCodeById = useMemo(() => {
    const map = new Map<string, string>();
    (marketsQ.data ?? []).forEach((m) => map.set(m.id, m.code));
    return map;
  }, [marketsQ.data]);

  const orders = ordersQ.data ?? [];
  const statusOptions = ["all", ...Array.from(new Set(orders.map((o) => o.status)))];
  const serviceOptions = ["all", ...Array.from(new Set(orders.map((o) => o.service_type)))];

  const filtered = orders.filter((o) => {
    if (status !== "all" && o.status !== status) return false;
    if (serviceType !== "all" && o.service_type !== serviceType) return false;
    if (market !== "all" && marketCodeById.get(o.market_id) !== market) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      if (!`${o.id} ${o.customer_id}`.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const columns: Column<Order>[] = [
    {
      header: "Order",
      cell: (o) => (
        <Link href={`/admin/orders/${o.id}`} className="font-medium text-brand hover:text-brand-hover">
          {shortId(o.id)}
        </Link>
      ),
    },
    { header: "Customer", cell: (o) => shortId(o.customer_id) },
    { header: "Market", cell: (o) => marketCodeById.get(o.market_id) ?? "-" },
    { header: "Service", cell: (o) => <span className="capitalize">{o.service_type.replace(/_/g, " ")}</span> },
    { header: "Status", cell: (o) => <StatusBadge status={o.status} /> },
    { header: "Total", cell: (o) => formatCurrency(o.estimated_total) },
    { header: "Payment", cell: (o) => <StatusBadge status={o.payment_status} /> },
    { header: "Channel", cell: (o) => <span className="capitalize">{o.source_channel}</span> },
    { header: "Created", cell: (o) => formatDateTime(o.created_at) },
  ];

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Orders created by the WhatsApp Operations Agent."
        actions={
          <Button variant="secondary" size="sm" onClick={() => ordersQ.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm capitalize text-ink"
        >
          {statusOptions.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : s}
            </option>
          ))}
        </select>

        <select
          value={serviceType}
          onChange={(e) => setServiceType(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm capitalize text-ink"
        >
          {serviceOptions.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All services" : s.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        <select
          value={market}
          onChange={(e) => setMarket(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink"
        >
          <option value="all">All markets</option>
          {(marketsQ.data ?? []).map((m) => (
            <option key={m.id} value={m.code}>
              {m.code}
            </option>
          ))}
        </select>

        <input
          type="search"
          placeholder="Search by order or customer id…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto min-w-[220px] flex-1 rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint"
        />
      </Card>

      <Card>
        {ordersQ.isLoading && <LoadingState label="Loading orders…" />}
        {ordersQ.error && !ordersQ.isLoading && (
          <ErrorState message={(ordersQ.error as Error).message} onRetry={() => ordersQ.refetch()} />
        )}
        {!ordersQ.isLoading && !ordersQ.error && filtered.length === 0 && (
          <EmptyState
            title="No orders match your filters"
            description="Orders appear once the WhatsApp Agent completes the happy path for a conversation."
          />
        )}
        {!ordersQ.isLoading && !ordersQ.error && filtered.length > 0 && (
          <DataTable columns={columns} rows={filtered} rowKey={(o) => o.id} />
        )}
      </Card>
    </div>
  );
}
