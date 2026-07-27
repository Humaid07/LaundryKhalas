import Link from "next/link";
import { ChevronRight, Phone, MapPin, Clock, Package } from "lucide-react";
import type { FacilityDriver } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/formatters";
import { driverRoleLabel, taskTypeLabel } from "@/lib/status";
import { DriverStatusBadge } from "./DriverStatusBadge";

/**
 * DriverCard — mobile-first preview of a driver: name, role, masked phone, live
 * status, and (when on a job) the current order ref, service, task, expected
 * completion and area. Never shows any customer PII — the payload carries none.
 */
export function DriverCard({ driver }: { driver: FacilityDriver }) {
  const assignment = driver.current_assignment ?? null;
  const orderRef = assignment?.order_ref ?? driver.current_order_ref ?? null;
  const task = assignment?.task_type ?? driver.current_task ?? null;

  return (
    <Link
      href={`/drivers/${driver.id}`}
      className="group flex items-stretch gap-4 rounded-2xl border border-border/70 bg-surface p-4 shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-[0.95rem] font-semibold text-ink">{driver.name}</p>
          <DriverStatusBadge driver={driver} />
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
          <span>{driverRoleLabel(driver.role)}</span>
          {driver.masked_phone && (
            <span className="inline-flex items-center gap-1">
              <Phone className="h-3 w-3" />
              {driver.masked_phone}
            </span>
          )}
          {driver.area && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {driver.area}
            </span>
          )}
        </div>

        {orderRef ? (
          <div className="mt-3 rounded-lg border border-border/60 bg-surface-2 px-3 py-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-rose">
                <Package className="h-3 w-3" />
                {orderRef}
              </span>
              {task && <span className="text-xs font-medium text-ink">{taskTypeLabel(task)}</span>}
            </div>
            {assignment?.service_summary && (
              <p className="mt-0.5 truncate text-xs text-ink-muted">{assignment.service_summary}</p>
            )}
            {assignment?.expected_completion_at && (
              <p className="mt-1 inline-flex items-center gap-1 text-xxs text-ink-faint">
                <Clock className="h-3 w-3" />
                Due {formatRelativeTime(assignment.expected_completion_at)}
              </p>
            )}
          </div>
        ) : (
          <p className="mt-3 text-xs text-ink-faint">
            {driver.last_active_at ? `Last active ${formatRelativeTime(driver.last_active_at)}` : "No active assignment"}
          </p>
        )}
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 self-center text-ink-faint transition-colors group-hover:text-rose" />
    </Link>
  );
}
