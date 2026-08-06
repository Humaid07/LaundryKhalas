import Link from "next/link";
import { ChevronRight, Clock, CheckCircle2, ShieldAlert, ArrowRight } from "lucide-react";
import type { FacilityOrder } from "@/lib/api-client";
import { formatRelativeTime, formatMoney } from "@/lib/formatters";
import { orderStatusLabel, orderStatusTone, slaLabel, slaTone, statusToken } from "@/lib/status";
import { StatusBadge } from "@/components/ui/primitives";
import { CardPhotoStrip } from "@/components/orders/PhotoViewer";

/** Lightweight next-action hint for the card (the detail view computes the
 *  backend-validated action list). Presentational only. */
const NEXT_ACTION_LABEL: Record<string, string> = {
  new: "Accept order",
  pending: "Accept order",
  active: "Accept order",
  pickup_scheduled: "Accept order",
  accepted: "Mark received",
  received: "Start processing",
  picked_up: "Start processing",
  in_cleaning: "Mark ready",
  cleaning: "Mark ready",
  qc: "Mark ready",
  quality_check: "Mark ready",
  ready: "Hand to driver",
  ready_for_delivery: "Hand to driver",
};

/**
 * OrderCard — the redesigned order preview. Leads with what the facility must DO
 * (Required Work), then surfaces critical/important notes, photo thumbnails,
 * fee and the next required action. The whole card links into the detail view.
 */
export function OrderCard({ order }: { order: FacilityOrder }) {
  const id = order.order_id ?? order.id;
  const service = order.service_display_name ?? order.service ?? "Order";
  const required = order.required_work_summary ?? [];
  const importantCount = order.important_note_count ?? 0;
  const previewIds = order.preview_photo_ids ?? [];
  const fee = order.facility_fee?.total;
  const feeCurrency = order.facility_fee?.currency ?? "AED";
  const isExpress = order.priority === "EXPRESS";
  const nextAction = NEXT_ACTION_LABEL[statusToken(order.status) ?? ""];

  return (
    <Link
      href={`/orders/${order.id}`}
      className="group block rounded-2xl border border-border/70 bg-surface p-4 shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
    >
      {/* Header: id + priority + status */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-semibold text-rose">{id}</span>
            {isExpress && (
              <StatusBadge tone="warning" dot={false}>Express</StatusBadge>
            )}
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
        </div>
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-ink-faint transition-colors group-hover:text-rose" />
      </div>

      {/* Required work — the headline operational content */}
      {required.length > 0 && (
        <div className="mt-3 rounded-xl border border-border/60 bg-surface-2 px-3.5 py-2.5">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Required work</p>
          <ul className="mt-1 space-y-1">
            {required.slice(0, 2).map((line, i) => (
              <li key={i} className="flex items-start gap-1.5 text-sm text-ink">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose" />
                <span className="min-w-0 truncate">{line}</span>
              </li>
            ))}
            {required.length > 2 && (
              <li className="pl-5 text-xxs text-ink-faint">+{required.length - 2} more</li>
            )}
          </ul>
        </div>
      )}

      {/* Important notes indicator */}
      {importantCount > 0 && (
        <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-warning/12 px-2.5 py-1 text-xs font-medium text-warning ring-1 ring-inset ring-warning/25">
          <ShieldAlert className="h-3.5 w-3.5" />
          {importantCount} important {importantCount === 1 ? "note" : "notes"}
        </div>
      )}

      {/* Photo thumbnails */}
      {previewIds.length > 0 && (
        <div className="mt-2.5">
          <CardPhotoStrip orderId={order.id} photoIds={previewIds} totalCount={order.photo_count} />
        </div>
      )}

      {/* Footer meta */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border/50 pt-2.5 text-xs text-ink-muted">
        {order.item_count != null && <span>{order.item_count} items</span>}
        {order.expected_completion_at && (
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Due {formatRelativeTime(order.expected_completion_at)}
          </span>
        )}
        {order.pickup_area && <span>{order.pickup_area}</span>}
        {fee != null && (
          <span className="font-medium text-ink">{formatMoney(fee, feeCurrency)}</span>
        )}
        {nextAction && (
          <span className="ml-auto inline-flex items-center gap-1 font-medium text-rose">
            {nextAction}
            <ArrowRight className="h-3 w-3" />
          </span>
        )}
      </div>
    </Link>
  );
}
