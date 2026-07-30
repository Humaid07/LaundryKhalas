import Link from "next/link";
import { ChevronRight, Clock } from "lucide-react";
import type { FacilityOrder } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/formatters";
import { orderStatusLabel, orderStatusTone, slaLabel, slaTone } from "@/lib/status";
import { StatusBadge } from "@/components/ui/primitives";
import { OrderPhotoBadge } from "@/components/orders/OrderPhotoBadge";

/**
 * OrderCard — the mobile-first order preview. Order id, service, expected time,
 * SLA status, status badge and a "View Details" affordance. The whole card is a
 * link into the full order detail page.
 */
export function OrderCard({ order }: { order: FacilityOrder }) {
  const id = order.order_id ?? order.id;
  const service = order.service_display_name ?? order.service ?? "Order";
  return (
    <Link
      href={`/orders/${order.id}`}
      className="group flex items-stretch gap-4 rounded-2xl border border-border/70 bg-surface p-4 shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs font-semibold text-rose">{id}</span>
          <StatusBadge tone={orderStatusTone(order.status)} dot={false}>
            {orderStatusLabel(order.status, order.status_label)}
          </StatusBadge>
          {order.sla_status && (
            <StatusBadge tone={slaTone(order.sla_status)} dot={false}>
              {slaLabel(order.sla_status)}
            </StatusBadge>
          )}
        </div>
        <p className="mt-1.5 truncate text-[0.95rem] font-semibold text-ink">{service}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
          {order.item_count != null && <span>{order.item_count} items</span>}
          {order.expected_at && (
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeTime(order.expected_at)}
            </span>
          )}
          {order.pickup_area && <span>{order.pickup_area}</span>}
          <OrderPhotoBadge
            status={order.status}
            intakeCount={order.intake_photo_count}
            preDispatchCount={order.pre_dispatch_photo_count}
          />
        </div>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 self-center text-ink-faint transition-colors group-hover:text-rose" />
    </Link>
  );
}
