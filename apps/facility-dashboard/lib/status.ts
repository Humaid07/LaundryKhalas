/** Maps backend status strings to UI tones + friendly labels. Everything is
 *  defensive: unknown values fall back to a neutral chip and a title-cased label. */
import type { Tone } from "./types";

function titleCase(s: string): string {
  return s
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

const ORDER_TONE: Record<string, Tone> = {
  new: "info",
  pending: "info",
  accepted: "info",
  received: "plum",
  picked_up: "plum",
  in_cleaning: "warning",
  cleaning: "warning",
  qc: "warning",
  quality_check: "warning",
  ready: "success",
  ready_for_delivery: "success",
  out_for_delivery: "plum",
  handoff: "success",
  completed: "success",
  delivered: "success",
  cancelled: "neutral",
  delayed: "danger",
  concern_raised: "danger",
  needs_attention: "danger",
};

export function orderStatusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return ORDER_TONE[status.toLowerCase()] ?? "neutral";
}

export function orderStatusLabel(
  status: string | null | undefined,
  fallbackLabel?: string | null,
): string {
  if (fallbackLabel) return fallbackLabel;
  if (!status) return "—";
  return titleCase(status);
}

const SLA_TONE: Record<string, Tone> = {
  on_track: "success",
  due_soon: "warning",
  overdue: "danger",
};

export function slaTone(sla: string | null | undefined): Tone {
  if (!sla) return "neutral";
  return SLA_TONE[sla.toLowerCase()] ?? "neutral";
}

export function slaLabel(sla: string | null | undefined): string {
  if (!sla) return "—";
  return titleCase(sla);
}

const ISSUE_TONE: Record<string, Tone> = {
  open: "warning",
  in_progress: "info",
  awaiting: "info",
  waiting: "info",
  resolved: "success",
  closed: "neutral",
};

export function issueStatusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return ISSUE_TONE[status.toLowerCase()] ?? "neutral";
}

export function issueStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return titleCase(status);
}

const OPERATING_TONE: Record<string, Tone> = {
  accepting: "success",
  open: "success",
  paused: "warning",
  closed: "neutral",
};

export function operatingTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return OPERATING_TONE[status.toLowerCase()] ?? "neutral";
}

export function operatingLabel(status: string | null | undefined): string {
  if (!status) return "Unknown";
  const s = status.toLowerCase();
  if (s === "accepting" || s === "open") return "Accepting orders";
  if (s === "paused") return "Paused";
  if (s === "closed") return "Closed";
  return titleCase(status);
}

/* ---------------------------------------------------------------- Drivers --- */

const DRIVER_TONE: Record<string, Tone> = {
  free: "success",
  available: "success",
  on_job: "info",
  on_break: "warning",
  break: "warning",
  offline: "neutral",
  inactive: "neutral",
  issue: "danger",
};

/** Tone for a driver's effective/raw status (free/on_job/on_break/offline/issue). */
export function driverStatusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return DRIVER_TONE[status.toLowerCase()] ?? "neutral";
}

const DRIVER_STATUS_LABELS: Record<string, string> = {
  free: "Available",
  available: "Available",
  on_job: "On Job",
  on_break: "On Break",
  offline: "Offline",
  issue: "Issue",
};

export function driverStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return DRIVER_STATUS_LABELS[status.toLowerCase()] ?? titleCase(status);
}

const TASK_TONE: Record<string, Tone> = {
  pickup: "info",
  facility_handoff: "plum",
  delivery: "plum",
  return: "warning",
};

export function taskTypeTone(task: string | null | undefined): Tone {
  if (!task) return "neutral";
  return TASK_TONE[task.toLowerCase()] ?? "neutral";
}

const TASK_LABELS: Record<string, string> = {
  pickup: "Pickup",
  facility_handoff: "Facility Handoff",
  delivery: "Delivery",
  return: "Return",
};

export function taskTypeLabel(task: string | null | undefined): string {
  if (!task) return "—";
  return TASK_LABELS[task.toLowerCase()] ?? titleCase(task);
}

const ASSIGNMENT_TONE: Record<string, Tone> = {
  assigned: "info",
  in_progress: "warning",
  completed: "success",
  cancelled: "neutral",
  issue: "danger",
};

export function assignmentStatusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return ASSIGNMENT_TONE[status.toLowerCase()] ?? "neutral";
}

export function assignmentStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return titleCase(status);
}

/** Human labels for the driver-role enum the backend returns. */
const DRIVER_ROLE_LABELS: Record<string, string> = {
  driver: "Driver",
  runner: "Runner",
  pickup_partner: "Pickup Partner",
};

export function driverRoleLabel(role: string | null | undefined): string {
  if (!role) return "Driver";
  return DRIVER_ROLE_LABELS[role.toLowerCase()] ?? titleCase(role);
}

/** Human labels for the status action verbs the backend accepts on an order. */
export const ACTION_LABELS: Record<string, string> = {
  accept: "Accept",
  mark_received: "Mark Received",
  start_cleaning: "Start Cleaning",
  move_to_qc: "Move to QC",
  mark_ready: "Mark Ready",
  confirm_handoff: "Confirm Handoff",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? titleCase(action);
}
