/** Maps backend status strings to UI tones + friendly labels. Everything is
 *  defensive: values arrive from Supabase/API and are treated as `unknown`, so a
 *  number/object/null never reaches a String method — it falls back to a neutral
 *  chip and a title-cased (or em-dash) label instead of crashing the page. */
import type { Tone } from "./types";

/** Coerce any untrusted backend value to a lowercased token ("" when unusable).
 *  Non-strings (object/array/null/undefined) yield "" so lookups miss cleanly;
 *  finite numbers stringify. This is the single guard in front of every
 *  `.toLowerCase()` in this module. */
function norm(value: unknown): string {
  if (typeof value === "string") return value.trim().toLowerCase();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

/** Safe lowercased token for equality checks / Set lookups against untrusted
 *  backend status values (never throws on a number/object/null). */
export function statusToken(value: unknown): string {
  return norm(value);
}

function titleCase(value: unknown): string {
  const s = typeof value === "string" ? value : norm(value);
  if (!s) return "—";
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

export function orderStatusTone(status: unknown): Tone {
  return ORDER_TONE[norm(status)] ?? "neutral";
}

export function orderStatusLabel(status: unknown, fallbackLabel?: string | null): string {
  if (typeof fallbackLabel === "string" && fallbackLabel.trim()) return fallbackLabel;
  if (!norm(status)) return "—";
  return titleCase(status);
}

const SLA_TONE: Record<string, Tone> = {
  on_track: "success",
  due_soon: "warning",
  overdue: "danger",
};

export function slaTone(sla: unknown): Tone {
  return SLA_TONE[norm(sla)] ?? "neutral";
}

export function slaLabel(sla: unknown): string {
  if (!norm(sla)) return "—";
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

export function issueStatusTone(status: unknown): Tone {
  return ISSUE_TONE[norm(status)] ?? "neutral";
}

export function issueStatusLabel(status: unknown): string {
  if (!norm(status)) return "—";
  return titleCase(status);
}

const OPERATING_TONE: Record<string, Tone> = {
  accepting: "success",
  open: "success",
  paused: "warning",
  closed: "neutral",
};

export function operatingTone(status: unknown): Tone {
  return OPERATING_TONE[norm(status)] ?? "neutral";
}

export function operatingLabel(status: unknown): string {
  const s = norm(status);
  if (!s) return "Unknown";
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
export function driverStatusTone(status: unknown): Tone {
  return DRIVER_TONE[norm(status)] ?? "neutral";
}

const DRIVER_STATUS_LABELS: Record<string, string> = {
  free: "Available",
  available: "Available",
  on_job: "On Job",
  on_break: "On Break",
  offline: "Offline",
  issue: "Issue",
};

export function driverStatusLabel(status: unknown): string {
  const s = norm(status);
  if (!s) return "—";
  return DRIVER_STATUS_LABELS[s] ?? titleCase(status);
}

const TASK_TONE: Record<string, Tone> = {
  pickup: "info",
  facility_handoff: "plum",
  delivery: "plum",
  return: "warning",
};

export function taskTypeTone(task: unknown): Tone {
  return TASK_TONE[norm(task)] ?? "neutral";
}

const TASK_LABELS: Record<string, string> = {
  pickup: "Pickup",
  facility_handoff: "Facility Handoff",
  delivery: "Delivery",
  return: "Return",
};

export function taskTypeLabel(task: unknown): string {
  const s = norm(task);
  if (!s) return "—";
  return TASK_LABELS[s] ?? titleCase(task);
}

const ASSIGNMENT_TONE: Record<string, Tone> = {
  assigned: "info",
  in_progress: "warning",
  completed: "success",
  cancelled: "neutral",
  issue: "danger",
};

export function assignmentStatusTone(status: unknown): Tone {
  return ASSIGNMENT_TONE[norm(status)] ?? "neutral";
}

export function assignmentStatusLabel(status: unknown): string {
  if (!norm(status)) return "—";
  return titleCase(status);
}

/** Human labels for the driver-role enum the backend returns. */
const DRIVER_ROLE_LABELS: Record<string, string> = {
  driver: "Driver",
  runner: "Runner",
  pickup_partner: "Pickup Partner",
};

export function driverRoleLabel(role: unknown): string {
  const s = norm(role);
  if (!s) return "Driver";
  return DRIVER_ROLE_LABELS[s] ?? titleCase(role);
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

export function actionLabel(action: unknown): string {
  const s = norm(action);
  return ACTION_LABELS[s] ?? titleCase(action);
}
