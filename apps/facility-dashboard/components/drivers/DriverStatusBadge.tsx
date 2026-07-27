import type { FacilityDriver } from "@/lib/api-client";
import { driverStatusLabel, driverStatusTone } from "@/lib/status";
import { StatusBadge } from "@/components/ui/primitives";

/**
 * DriverStatusBadge — a colored chip for a driver's live status. Prefers the
 * backend-decorated `effective_status` (free/on_job/on_break/offline/issue),
 * falling back to the raw `status` string. Free=positive, on_job=info,
 * on_break=amber, offline=muted, issue=danger.
 */
export function DriverStatusBadge({
  driver,
  status,
  dot = false,
}: {
  driver?: Pick<FacilityDriver, "effective_status" | "status" | "active">;
  status?: string | null;
  dot?: boolean;
}) {
  const raw = status ?? driver?.effective_status ?? driver?.status;
  return (
    <StatusBadge tone={driverStatusTone(raw)} dot={dot}>
      {driverStatusLabel(raw)}
    </StatusBadge>
  );
}
