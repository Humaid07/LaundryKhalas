import { facilityOrders, type FacilityOrder } from "@/lib/dashboard/operations-data";

/** Look up a single facility order by id for its detail page. */
export function getFacilityOrder(id: string): FacilityOrder | undefined {
  return facilityOrders.find((o) => o.id === id);
}

export const FACILITY_LIFECYCLE: FacilityOrder["status"][] = [
  "Awaiting Assignment",
  "In Cleaning",
  "Quality Check",
  "Ready for Delivery",
];
