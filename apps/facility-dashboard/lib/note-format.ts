import type { Tone } from "@/lib/types";
import type { NotePriority } from "@/lib/api-client";

/** Human labels for the grouped-note SECTION keys returned by the view serializer. */
export const NOTE_SECTION_LABELS: Record<string, string> = {
  customer_instructions: "Customer Instructions",
  pickup_instructions: "Pickup Instructions",
  delivery_instructions: "Delivery Instructions",
  access_instructions: "Building & Access Instructions",
  contact_preferences: "Contact Preferences",
  timing_preferences: "Timing Preferences",
  item_handling: "Item Handling",
  stains: "Stains",
  existing_damage: "Existing Damage",
  special_care: "Special Care",
  inspection_requirements: "Inspection Requirements",
  operations_notes: "Operations Notes",
  amendments: "Post-confirmation Amendments",
};

/** The order sections render in — critical/handling info before routine notes. */
export const NOTE_SECTION_ORDER: string[] = [
  "existing_damage",
  "special_care",
  "item_handling",
  "stains",
  "inspection_requirements",
  "customer_instructions",
  "pickup_instructions",
  "delivery_instructions",
  "access_instructions",
  "contact_preferences",
  "timing_preferences",
  "operations_notes",
  "amendments",
];

/** Priority → design tone. CRITICAL gets the strong warning treatment; IMPORTANT
 *  a softer warning; NORMAL stays neutral (no decorative colour for routine notes). */
export function priorityTone(priority: NotePriority | string | null | undefined): Tone {
  switch (priority) {
    case "CRITICAL":
      return "danger";
    case "IMPORTANT":
      return "warning";
    default:
      return "neutral";
  }
}

export function priorityLabel(priority: NotePriority | string | null | undefined): string {
  switch (priority) {
    case "CRITICAL":
      return "Critical";
    case "IMPORTANT":
      return "Important";
    default:
      return "Note";
  }
}

/** Human labels for photo source provenance. */
export const PHOTO_SOURCE_LABELS: Record<string, string> = {
  CUSTOMER: "Customer",
  DRIVER: "Driver",
  OPERATIONS: "Operations",
  FACILITY_BEFORE_PROCESSING: "Before processing",
  FACILITY_AFTER_PROCESSING: "After processing",
  FACILITY_ISSUE: "Issue photo",
  INSPECTION: "Inspection",
};

export function photoSourceLabel(source: string | null | undefined): string {
  if (!source) return "Photo";
  return PHOTO_SOURCE_LABELS[source] ?? source;
}
