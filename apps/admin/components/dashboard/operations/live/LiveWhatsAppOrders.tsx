"use client";

import { MapPin, RefreshCw, Radio, AlertTriangle, PackageOpen } from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import { formatCurrency } from "@/lib/dashboard/formatters";
import type { Tone } from "@/lib/dashboard/types";
import { agentApi, type OrderDTO } from "@/lib/dashboard/whatsapp-agent-api";
import { LIVE_WHATSAPP_ENABLED, useLiveAgentData } from "./useLiveAgentData";

/** Live order status → badge tone. Covers the backend order-state model. */
function liveStatusTone(status: string): Tone {
  const s = (status || "").toLowerCase();
  if (["completed", "delivered"].includes(s)) return "success";
  if (["cancelled"].includes(s)) return "danger";
  if (["draft"].includes(s)) return "neutral";
  if (["support_required", "cancellation_requested", "pickup_change_requested"].includes(s))
    return "warning";
  return "info";
}

const columns: Column<OrderDTO>[] = [
  {
    key: "order_id",
    header: "Order ID",
    primary: true,
    cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.order_id}</span>,
  },
  { key: "customer", header: "Customer", cell: (o) => <span className="whitespace-nowrap text-ink">{o.customer_name ?? "—"}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service_display_name ?? o.service_type ?? "—"}</span> },
  {
    // Privacy: broad tables show area/city only — never the full pickup address.
    key: "geo",
    header: "City / Area",
    cell: (o) => (
      <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted">
        <MapPin className="h-3 w-3 text-ink-faint" />
        {[o.pickup_area, o.city].filter(Boolean).join(", ") || "—"}
      </span>
    ),
  },
  { key: "pickup", header: "Pickup date", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{(o.pickup_date as string) ?? "—"}</span> },
  { key: "pickup_time", header: "Pickup time", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{(o.pickup_time as string) ?? "—"}</span> },
  { key: "instructions", header: "Instructions", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{(o.pickup_instructions as string) ?? "—"}</span> },
  { key: "status", header: "Status", cell: (o) => <StatusBadge tone={liveStatusTone(o.status)}>{o.status_label || o.status}</StatusBadge> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{o.amount != null ? formatCurrency(o.amount) : "—"}</span> },
  { key: "payment", header: "Payment", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{o.payment ?? "—"}</span> },
];

/**
 * Live WhatsApp-created orders, read from the agent backend
 * (Dashboard → FastAPI → Supabase, GET /api/orders). Rendered only when
 * NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true; otherwise nothing renders and the
 * existing demo order surfaces are unaffected.
 */
export function LiveWhatsAppOrders() {
  const { data, loading, error, refresh } = useLiveAgentData<OrderDTO[]>(() => agentApi.listOrders());
  if (!LIVE_WHATSAPP_ENABLED) return null;

  const rows = data ?? [];

  return (
    <Panel padded={false}>
      <PanelHeader
        title="Live WhatsApp orders"
        subtitle="Orders created by the WhatsApp agent · live from /api/orders"
        className="p-4"
        action={
          <div className="flex items-center gap-2">
            <StatusBadge tone="info" dot><span className="inline-flex items-center gap-1"><Radio className="h-3 w-3" /> Live</span></StatusBadge>
            <Button size="sm" variant="secondary" onClick={refresh} aria-label="Refresh live orders">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          </div>
        }
      />
      <div className="px-4 pb-4">
        {loading ? (
          <LoadingState label="Loading live orders…" />
        ) : error ? (
          <EmptyState
            icon={AlertTriangle}
            title="Backend unavailable"
            description={error}
            action={<Button size="sm" variant="secondary" onClick={refresh}>Try again</Button>}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(o) => o.id}
            empty={<EmptyState icon={PackageOpen} title="No live orders yet" description="Orders booked over WhatsApp will appear here as customers confirm." />}
            onRowLabel={(o) => <StatusBadge tone={liveStatusTone(o.status)}>{o.status_label || o.status}</StatusBadge>}
          />
        )}
      </div>
    </Panel>
  );
}
