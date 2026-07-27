import { User } from "lucide-react";
import type { FacilityDriver } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/formatters";
import { driverRoleLabel } from "@/lib/status";
import { DetailSectionCard, Field, FieldGrid } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";

/**
 * DriverDetailHeader — the "At a glance" identity card on the driver detail
 * page: masked phone, role, vehicle, area, active/offline and last-active time.
 * The page title + live status badge live in the page shell above this.
 */
export function DriverDetailHeader({ driver }: { driver: FacilityDriver }) {
  return (
    <DetailSectionCard title="At a glance" icon={User}>
      <FieldGrid cols={2}>
        <Field label="Role" value={driverRoleLabel(driver.role)} />
        <Field
          label="Contact"
          value={driver.masked_phone ?? "—"}
          mono={!!driver.masked_phone}
        />
        <Field label="Vehicle" value={driver.vehicle_type ?? "—"} />
        <Field label="Area" value={driver.area ?? "—"} />
        <Field
          label="Availability"
          value={
            <StatusBadge tone={driver.active === false ? "neutral" : "success"} dot={false}>
              {driver.active === false ? "Offline" : "Active"}
            </StatusBadge>
          }
        />
        <Field label="Last active" value={formatRelativeTime(driver.last_active_at)} />
      </FieldGrid>
    </DetailSectionCard>
  );
}
