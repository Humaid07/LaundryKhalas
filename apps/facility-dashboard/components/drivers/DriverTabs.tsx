import type { FacilityDriver, DriverSummary } from "@/lib/api-client";
import { WorkflowTabs } from "@/components/ui/Tabs";

export const DRIVER_FILTERS = [
  { id: "all", label: "All Drivers" },
  { id: "free", label: "Free" },
  { id: "on_job", label: "On Job" },
  { id: "pickup", label: "Pickup" },
  { id: "delivery", label: "Delivery" },
  { id: "issue", label: "Issues" },
] as const;

export type DriverFilter = (typeof DRIVER_FILTERS)[number]["id"];

/** Current task for a driver — prefers the decorated assignment's task type. */
function currentTask(d: FacilityDriver): string | null {
  return d.current_assignment?.task_type ?? d.current_task ?? null;
}

/** Client-side filter matching the active tab. */
export function matchesDriverFilter(d: FacilityDriver, filter: DriverFilter): boolean {
  const status = d.effective_status ?? d.status;
  switch (filter) {
    case "free":
      return d.is_free === true || status === "free";
    case "on_job":
      return status === "on_job";
    case "pickup":
      return currentTask(d) === "pickup";
    case "delivery":
      return currentTask(d) === "delivery";
    case "issue":
      return status === "issue";
    case "all":
    default:
      return true;
  }
}

/** Per-tab counts from the summary envelope (falls back to 0). */
function countFor(filter: DriverFilter, summary?: DriverSummary): number | undefined {
  if (!summary) return undefined;
  switch (filter) {
    case "all":
      return summary.total;
    case "free":
      return summary.free;
    case "on_job":
      return summary.on_job;
    case "pickup":
      return summary.pickup;
    case "delivery":
      return summary.delivery;
    case "issue":
      return summary.issues;
    default:
      return undefined;
  }
}

/**
 * DriverTabs — the sticky filter row for the drivers list. Thin wrapper over
 * WorkflowTabs that carries the driver filter set and per-tab counts.
 */
export function DriverTabs({
  value,
  onChange,
  summary,
}: {
  value: DriverFilter;
  onChange: (id: DriverFilter) => void;
  summary?: DriverSummary;
}) {
  const tabs = DRIVER_FILTERS.map((f) => ({
    id: f.id,
    label: f.label,
    count: countFor(f.id, summary),
  }));
  return <WorkflowTabs tabs={tabs} value={value} onChange={(id) => onChange(id as DriverFilter)} />;
}
