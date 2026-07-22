import type { Tone } from "./types";

/**
 * Display metadata for the backend order-status model (services/order_store.py
 * ORDER_STATUSES). The spec's suggested names are mapped onto the existing valid
 * statuses (processing ← in_cleaning, ready ← ready_for_delivery) rather than
 * introducing duplicates.
 */
export const ORDER_STATUS_META: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  active: { label: "Active", tone: "info" },
  confirmed: { label: "Confirmed", tone: "info" },
  pickup_scheduled: { label: "Pickup Scheduled", tone: "info" },
  picked_up: { label: "Picked Up", tone: "plum" },
  in_cleaning: { label: "Processing", tone: "plum" },
  ready_for_delivery: { label: "Ready", tone: "warning" },
  out_for_delivery: { label: "Out for Delivery", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  abandoned: { label: "Abandoned", tone: "neutral" },
  support_required: { label: "Needs Attention", tone: "danger" },
  cancellation_requested: { label: "Cancellation Requested", tone: "warning" },
  pickup_change_requested: { label: "Pickup Change", tone: "warning" },
};

export function statusMeta(status: string | null | undefined): { label: string; tone: Tone } {
  return ORDER_STATUS_META[status ?? ""] ?? { label: status ?? "—", tone: "neutral" };
}

/**
 * Forward operational statuses an operator may set from the dashboard. These are
 * all backend-valid (set_status validates against ORDER_STATUSES); the backend
 * remains the authority — this list only controls what the UI offers.
 */
export const DASHBOARD_STATUS_OPTIONS = [
  "pickup_scheduled",
  "picked_up",
  "in_cleaning",
  "ready_for_delivery",
  "out_for_delivery",
  "completed",
  "cancelled",
];

/** View tab → search params for the Orders section. */
export const ORDER_VIEWS: Record<
  string,
  { label: string; params: { status?: string; needs_attention?: boolean; sort?: string } }
> = {
  all: { label: "All Orders", params: { sort: "new" } },
  new: { label: "New", params: { sort: "new", status: "draft" } },
  active: { label: "Active", params: { sort: "pickup", status: "pickup_scheduled" } },
  attention: { label: "Needs Attention", params: { needs_attention: true, sort: "attention" } },
  completed: { label: "Completed", params: { status: "completed", sort: "updated" } },
  cancelled: { label: "Cancelled", params: { status: "cancelled", sort: "updated" } },
};
