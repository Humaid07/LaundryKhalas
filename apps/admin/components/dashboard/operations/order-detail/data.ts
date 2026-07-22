/**
 * Derivation helpers for the Customer Order detail page. Pure + deterministic
 * (no Date.now / Math.random — event timestamps are derived from the order's
 * createdAt so server and client render identically). All data here is mock; it
 * exists only to exercise the detail UI. Nothing is invented about a real order.
 */
import type { Order, OrderStatus, Tone } from "@/lib/dashboard/types";
import { orders, conversations } from "@/lib/dashboard/mock-data";
import { MOCK_NOW } from "@/lib/dashboard/formatters";
import {
  facilityOrders, orderIssues, nextStepByStatus, orderSla,
  type QualityResult,
} from "@/lib/dashboard/operations-data";

export const LIFECYCLE: OrderStatus[] = [
  "New", "Pickup Scheduled", "Driver Assigned", "Picked Up",
  "In Cleaning", "Ready for Delivery", "Out for Delivery", "Delivered",
];

export function getOrder(id: string): Order | undefined {
  return orders.find((o) => o.id === id);
}

export function itemCount(o: Order): number {
  return o.items.reduce((s, i) => s + i.qty, 0);
}

/* ------------------------------ lifecycle timeline -------------------------- */

export type StepState = "done" | "current" | "future";
export interface LifecycleStep {
  label: OrderStatus;
  state: StepState;
  at?: string;
  actor?: string;
  note?: string;
}

const STEP_ACTOR: Partial<Record<OrderStatus, string>> = {
  New: "WhatsApp Agent",
  "Pickup Scheduled": "Operations",
  "Driver Assigned": "Dispatch",
  "Picked Up": "Driver",
  "In Cleaning": "Facility",
  "Ready for Delivery": "Facility",
  "Out for Delivery": "Driver",
  Delivered: "Driver",
};

/**
 * ISO time for a step the order has already reached, anchored between the order's
 * creation and "now" (MOCK_NOW). Step 0 lands on `createdAt`, the current step
 * lands on ~now, and intermediate steps spread across that span — so a COMPLETED
 * step is always in the past and nothing already done ever renders as a future
 * "in X" timestamp. Deterministic (no Date.now): server and client agree.
 */
function stepTime(o: Order, index: number): string {
  const created = new Date(o.createdAt).getTime();
  const now = new Date(MOCK_NOW).getTime();
  const currentIdx = LIFECYCLE.indexOf(o.status);
  if (currentIdx <= 0 || now <= created) return o.createdAt;
  const clamped = Math.min(Math.max(index, 0), currentIdx);
  return new Date(created + ((now - created) * clamped) / currentIdx).toISOString();
}

export function lifecycleSteps(o: Order): LifecycleStep[] {
  const currentIdx = LIFECYCLE.indexOf(o.status);
  return LIFECYCLE.map((label, i) => {
    const state: StepState = currentIdx < 0 ? "future" : i < currentIdx ? "done" : i === currentIdx ? "current" : "future";
    return {
      label,
      state,
      at: state === "future" ? undefined : stepTime(o, i),
      actor: state === "future" ? undefined : STEP_ACTOR[label],
    };
  });
}

export const isCancelled = (o: Order) => o.status === "Cancelled";
export const isFlagged = (o: Order) => o.status === "Concern Raised";

/* -------------------------------- derivations ------------------------------ */

export type Priority = "Urgent" | "High" | "Standard";

export function orderPriority(o: Order): Priority {
  if (o.status === "Concern Raised") return "Urgent";
  if (o.channel === "B2B" || o.amount >= 500) return "High";
  return "Standard";
}

export const priorityTone: Record<Priority, Tone> = {
  Urgent: "danger",
  High: "warning",
  Standard: "neutral",
};

export function customerType(o: Order): string {
  if (o.channel === "B2B" || /\(B2B\)/i.test(o.customer)) return "Business / B2B";
  return "Individual";
}

export function customerStats(o: Order): { totalOrders: number; lastOrderDate: string } {
  const mine = orders.filter((x) => x.customer === o.customer);
  const last = mine.reduce((a, b) => (a.createdAt > b.createdAt ? a : b), mine[0]);
  return { totalOrders: mine.length, lastOrderDate: last.createdAt };
}

/** Delivery-slot read-out. Status-derived (no invented times). */
export function deliverySlotLabel(o: Order): string {
  switch (o.status) {
    case "Delivered": return "Delivered";
    case "Out for Delivery": return "Out for delivery now";
    case "Ready for Delivery": return "Ready — scheduling delivery";
    case "Cancelled": return "—";
    default: return "After cleaning & QC";
  }
}

export function pendingAmount(o: Order): number {
  return o.payment === "Pending" ? o.amount : 0;
}

export function qcStatus(o: Order): QualityResult {
  const fo = facilityOrders.find((f) => f.id === o.id);
  if (fo) return fo.quality;
  if (o.status === "Delivered" || o.status === "Ready for Delivery" || o.status === "Out for Delivery") return "Passed";
  if (o.status === "In Cleaning") return "Pending";
  return "N/A";
}

export function relatedConversation(o: Order) {
  return conversations.find((c) => c.assignedOrder === o.id) ?? null;
}

export function relatedIssues(o: Order) {
  return orderIssues.filter((i) => i.orderId === o.id);
}

export function nextStep(o: Order): string {
  return nextStepByStatus[o.status] ?? "—";
}

export function sla(o: Order) {
  return orderSla(o.status);
}

/* --------------------------------- events ---------------------------------- */

export interface OrderEvent {
  id: string;
  label: string;
  detail?: string;
  actor: string;
  at: string;
  tone: Tone;
}

/** A deterministic audit feed built from the order's known facts. */
export function orderEvents(o: Order): OrderEvent[] {
  const events: OrderEvent[] = [];
  const at = (i: number) => stepTime(o, i);

  events.push({ id: "e-created", label: "Order created", detail: `${o.service} · via ${o.channel}`, actor: STEP_ACTOR.New ?? "System", at: o.createdAt, tone: "info" });

  const currentIdx = LIFECYCLE.indexOf(o.status);
  if (o.facility && currentIdx >= 1) events.push({ id: "e-facility", label: "Facility assigned", detail: o.facility, actor: "Operations", at: at(1), tone: "info" });
  if (o.driver && currentIdx >= 2) events.push({ id: "e-driver", label: "Driver assigned", detail: o.driver, actor: "Dispatch", at: at(2), tone: "info" });
  if (currentIdx >= 0) events.push({ id: "e-status", label: `Status → ${o.status}`, actor: STEP_ACTOR[o.status] ?? "System", at: at(Math.max(currentIdx, 3)), tone: "rose" });

  if (isFlagged(o)) events.push({ id: "e-concern", label: "Concern raised on order", detail: "Escalated for review", actor: "Support", at: at(6), tone: "danger" });
  if (isCancelled(o)) events.push({ id: "e-cancel", label: "Cancellation processed", detail: o.payment === "Refunded" ? "Refund issued" : undefined, actor: "Operations", at: at(2), tone: "warning" });

  for (const iss of relatedIssues(o)) {
    events.push({ id: `e-iss-${iss.id}`, label: `Issue: ${iss.issueType}`, detail: iss.assignedTeam, actor: "Support", at: iss.lastUpdate, tone: "warning" });
  }

  // newest first
  return events.sort((a, b) => (a.at < b.at ? 1 : -1));
}

/* ---------------------------------- notes ---------------------------------- */

export interface InternalNote {
  id: string;
  author: string;
  at: string;
  body: string;
}

/** Minimal deterministic seed so the notes panel isn't empty on flagged orders. */
export function seedNotes(o: Order): InternalNote[] {
  if (isFlagged(o)) {
    return [{ id: "n1", author: "Quality — Huda", at: o.createdAt, body: "Customer reported a quality concern. Re-check before any handoff and log the outcome." }];
  }
  if (o.channel === "B2B") {
    return [{ id: "n1", author: "Ops — Faris", at: o.createdAt, body: "B2B account — confirm consolidated invoice and delivery window with the account contact." }];
  }
  return [];
}
