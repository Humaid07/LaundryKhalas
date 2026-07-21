/**
 * Operations mock data, split by team: Customer Facing vs Facility Facing.
 * Deterministic, LaundryKhalas-specific, mock-only.
 *
 * PRIVACY: Facility-facing records intentionally carry NO customer PII —
 * area/city only, no name, phone, email, full address or complaint notes.
 * Customer-facing records mask phone numbers via `maskPhone`.
 */
import type { KpiStat, Tone } from "./types";

/* ============================== CUSTOMER FACING ============================== */

export const customerFacingKpis: KpiStat[] = [
  { label: "Open Conversations", value: "24", delta: 6.2, tone: "rose", spark: [16, 18, 19, 21, 20, 22, 24], hint: "Across WhatsApp, web & app" },
  { label: "Pending Customer Replies", value: "7", delta: -12.0, tone: "warning", spark: [11, 10, 9, 9, 8, 8, 7] },
  { label: "Active Tickets", value: "12", delta: -4.0, tone: "info", spark: [15, 14, 14, 13, 13, 12, 12] },
  { label: "Pending Cancellations", value: "3", delta: 1.0, tone: "danger", spark: [1, 2, 2, 2, 3, 2, 3] },
  { label: "Order Change Requests", value: "5", delta: 2.0, tone: "plum", spark: [2, 3, 3, 4, 4, 5, 5] },
  { label: "Escalated Concerns", value: "2", delta: 0, tone: "warning", spark: [3, 2, 2, 3, 2, 2, 2] },
  { label: "Refund Requests", value: "4", delta: 1.0, tone: "danger", spark: [2, 2, 3, 3, 3, 4, 4], hint: "Awaiting Finance review" },
  { label: "Avg Response Time", value: "2m 40s", delta: -8.3, tone: "success", spark: [3.4, 3.2, 3.1, 2.9, 2.8, 2.7, 2.6], hint: "First human/AI response" },
];

export interface Cancellation {
  id: string;
  orderId: string;
  customer: string;
  phone: string;
  reason: string;
  refund: number;
  requestedAt: string;
  status: "Awaiting Approval" | "Approved" | "Declined";
}

export const cancellations: Cancellation[] = [
  { id: "CX-3011", orderId: "LK-24807", customer: "Reem Fahad", phone: "+966 56 771 2093", reason: "Ordered by mistake", refund: 0, requestedAt: "2026-07-20T08:15:00Z", status: "Awaiting Approval" },
  { id: "CX-3012", orderId: "LK-24815", customer: "Fatima Al-Suwaidi", phone: "+974 33 118 2245", reason: "Found another provider", refund: 120, requestedAt: "2026-07-20T09:02:00Z", status: "Awaiting Approval" },
  { id: "CX-3013", orderId: "LK-24810", customer: "Khalid Nasser", phone: "+965 99 220 8841", reason: "Pickup slot no longer works", refund: 0, requestedAt: "2026-07-20T09:20:00Z", status: "Awaiting Approval" },
];

export interface OrderChange {
  id: string;
  orderId: string;
  customer: string;
  change: string;
  risk: "Low" | "Medium";
  requestedAt: string;
  status: "Awaiting Approval" | "Applied";
}

export const orderChanges: OrderChange[] = [
  { id: "CH-5501", orderId: "LK-24810", customer: "Khalid Nasser", change: "Reschedule pickup → tomorrow 13:00–15:00", risk: "Low", requestedAt: "2026-07-20T09:05:00Z", status: "Awaiting Approval" },
  { id: "CH-5502", orderId: "LK-24815", customer: "Fatima Al-Suwaidi", change: "Add 1 king duvet to order", risk: "Low", requestedAt: "2026-07-20T08:40:00Z", status: "Awaiting Approval" },
  { id: "CH-5503", orderId: "LK-24812", customer: "Hassan Ali", change: "Re-clean marked curtain panel", risk: "Medium", requestedAt: "2026-07-20T09:22:00Z", status: "Awaiting Approval" },
  { id: "CH-5504", orderId: "LK-24817", customer: "Aisha Rahman", change: "Change delivery address to office", risk: "Medium", requestedAt: "2026-07-20T09:30:00Z", status: "Awaiting Approval" },
  { id: "CH-5505", orderId: "LK-24809", customer: "Sara Juma", change: "Add express turnaround", risk: "Low", requestedAt: "2026-07-20T07:10:00Z", status: "Applied" },
];

export interface Followup {
  id: string;
  customer: string;
  city: string;
  reason: string;
  channel: string;
  due: string;
  status: "Due" | "Scheduled" | "Done";
}

export const customerFollowups: Followup[] = [
  { id: "FU-7001", customer: "Hassan Ali", city: "Sharjah", reason: "Confirm curtain re-clean resolved the mark", channel: "WhatsApp", due: "2026-07-20T14:00:00Z", status: "Due" },
  { id: "FU-7002", customer: "Layla Kareem", city: "Riyadh", reason: "Post-delivery satisfaction check", channel: "WhatsApp", due: "2026-07-20T17:00:00Z", status: "Scheduled" },
  { id: "FU-7003", customer: "Grand Bay Hotel", city: "Doha", reason: "B2B weekly pickup confirmation", channel: "Email", due: "2026-07-21T09:00:00Z", status: "Scheduled" },
  { id: "FU-7004", customer: "Omar Haddad", city: "Abu Dhabi", reason: "Share 'in cleaning' status + ready-by", channel: "WhatsApp", due: "2026-07-20T11:30:00Z", status: "Done" },
];

export interface OpsActivity {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
}

export const customerActivity: OpsActivity[] = [
  { id: "ca1", title: "New WhatsApp pickup request", detail: "Aisha Rahman · Wash & Fold · Dubai Marina", time: "2026-07-20T09:40:00Z", tone: "rose" },
  { id: "ca2", title: "Reply drafted, awaiting approval", detail: "Omar Haddad · share 'In Cleaning' status", time: "2026-07-20T09:38:00Z", tone: "warning" },
  { id: "ca3", title: "Human takeover started", detail: "Hassan Ali · curtain quality concern", time: "2026-07-20T09:22:00Z", tone: "info" },
  { id: "ca4", title: "Cancellation requested", detail: "Fatima Al-Suwaidi · order LK-24815", time: "2026-07-20T09:02:00Z", tone: "danger" },
  { id: "ca5", title: "Order change requested", detail: "Khalid Nasser · reschedule pickup", time: "2026-07-20T09:05:00Z", tone: "plum" },
];

/* ============================== FACILITY FACING ============================= */

export const facilityFacingKpis: KpiStat[] = [
  { label: "Awaiting Assignment", value: "9", delta: 3.0, tone: "warning", spark: [4, 5, 6, 7, 8, 8, 9], hint: "Orders with no facility yet" },
  { label: "In Cleaning", value: "218", delta: 4.5, tone: "info", spark: [188, 196, 202, 208, 212, 215, 218] },
  { label: "Delayed at Facility", value: "6", delta: 20.0, tone: "danger", spark: [3, 3, 4, 4, 5, 5, 6] },
  { label: "Quality Check Pending", value: "14", delta: -6.0, tone: "plum", spark: [18, 17, 16, 16, 15, 14, 14] },
  { label: "Ready for Delivery", value: "41", delta: 9.0, tone: "success", spark: [28, 31, 33, 36, 38, 40, 41] },
  { label: "Facility Issues Open", value: "3", delta: 1.0, tone: "warning", spark: [1, 2, 2, 2, 3, 2, 3] },
  { label: "Top Facility", value: "Marina Hub", tone: "rose", hint: "PPI 96 · 22h turnaround" },
  { label: "Avg Turnaround", value: "22h", delta: -5.2, tone: "success", spark: [26, 25, 24, 24, 23, 22, 22], hint: "Pickup received → ready" },
];

export interface Facility {
  name: string;
  city: string;
  area: string;
  activeOrders: number;
  capacity: number;
  loadPct: number;
  ppiScore: number;
  delayedOrders: number;
  status: "Operational" | "High load" | "At capacity" | "Delayed";
}

export const facilities: Facility[] = [
  { name: "Marina Hub", city: "Dubai", area: "Dubai Marina", activeOrders: 84, capacity: 120, loadPct: 70, ppiScore: 96, delayedOrders: 0, status: "Operational" },
  { name: "Al Quoz Plant", city: "Dubai", area: "Al Quoz", activeOrders: 142, capacity: 160, loadPct: 89, ppiScore: 91, delayedOrders: 2, status: "High load" },
  { name: "Khalidiya Plant", city: "Abu Dhabi", area: "Khalidiya", activeOrders: 76, capacity: 110, loadPct: 69, ppiScore: 93, delayedOrders: 1, status: "Operational" },
  { name: "West Bay Hub", city: "Doha", area: "West Bay", activeOrders: 58, capacity: 60, loadPct: 97, ppiScore: 88, delayedOrders: 3, status: "At capacity" },
  { name: "Olaya Hub", city: "Riyadh", area: "Olaya", activeOrders: 44, capacity: 90, loadPct: 49, ppiScore: 90, delayedOrders: 0, status: "Operational" },
  { name: "Seef Hub", city: "Manama", area: "Seef", activeOrders: 22, capacity: 50, loadPct: 44, ppiScore: 94, delayedOrders: 0, status: "Operational" },
];

export type QualityResult = "Pending" | "Passed" | "Failed" | "N/A";

export interface FacilityOrder {
  id: string;
  facility: string;
  service: string;
  items: number;
  area: string; // customer AREA/CITY only — no name, phone or full address
  status: "Awaiting Assignment" | "In Cleaning" | "Quality Check" | "Delayed" | "Ready for Delivery";
  priority: "Urgent" | "High" | "Standard";
  pickupReceived: string;
  expectedCompletion: string;
  quality: QualityResult;
}

export const facilityOrders: FacilityOrder[] = [
  { id: "LK-24816", facility: "Khalidiya Plant", service: "Dry Cleaning", items: 3, area: "Abu Dhabi · Khalidiya", status: "In Cleaning", priority: "Standard", pickupReceived: "2026-07-20T08:55:00Z", expectedCompletion: "2026-07-21T10:00:00Z", quality: "N/A" },
  { id: "LK-24808", facility: "West Bay Hub", service: "Business Laundry", items: 360, area: "Doha · West Bay", status: "Delayed", priority: "Urgent", pickupReceived: "2026-07-20T05:10:00Z", expectedCompletion: "2026-07-20T18:00:00Z", quality: "N/A" },
  { id: "LK-24811", facility: "Seef Hub", service: "Wash & Fold", items: 1, area: "Manama · Seef", status: "Ready for Delivery", priority: "Standard", pickupReceived: "2026-07-20T06:20:00Z", expectedCompletion: "2026-07-20T12:00:00Z", quality: "Passed" },
  { id: "LK-24812", facility: "Industrial Area Plant", service: "Curtains / Upholstery", items: 8, area: "Sharjah · Al Nahda", status: "Quality Check", priority: "High", pickupReceived: "2026-07-19T15:40:00Z", expectedCompletion: "2026-07-20T16:00:00Z", quality: "Pending" },
  { id: "LK-24817", facility: "Marina Hub", service: "Wash & Fold", items: 10, area: "Dubai · Dubai Marina", status: "Ready for Delivery", priority: "Standard", pickupReceived: "2026-07-20T09:20:00Z", expectedCompletion: "2026-07-20T15:00:00Z", quality: "Passed" },
  { id: "LK-24814", facility: "Al Quoz Plant", service: "Business Laundry", items: 100, area: "Dubai · Business Bay", status: "In Cleaning", priority: "High", pickupReceived: "2026-07-20T07:30:00Z", expectedCompletion: "2026-07-21T09:00:00Z", quality: "N/A" },
  { id: "LK-24810", facility: "—", service: "Dry Cleaning", items: 3, area: "Kuwait City · Salmiya", status: "Awaiting Assignment", priority: "Standard", pickupReceived: "—", expectedCompletion: "—", quality: "N/A" },
  { id: "LK-24818", facility: "—", service: "Blankets / Duvets", items: 2, area: "Dubai · JLT", status: "Awaiting Assignment", priority: "High", pickupReceived: "—", expectedCompletion: "—", quality: "N/A" },
];

export interface FacilityIssue {
  id: string;
  facility: string;
  city: string; // facility city — for global geo filters
  issue: string;
  severity: "Critical" | "High" | "Medium";
  status: "Open" | "Investigating" | "Resolved";
  raisedAt: string;
}

export const facilityIssues: FacilityIssue[] = [
  { id: "FI-201", facility: "West Bay Hub", city: "Doha", issue: "Over capacity — 3 orders at risk of delay", severity: "High", status: "Investigating", raisedAt: "2026-07-20T06:00:00Z" },
  { id: "FI-202", facility: "Industrial Area Plant", city: "Sharjah", issue: "Steam press unit #2 down", severity: "Medium", status: "Open", raisedAt: "2026-07-20T07:45:00Z" },
  { id: "FI-203", facility: "Al Quoz Plant", city: "Dubai", issue: "Detergent stock low (<1 day)", severity: "Medium", status: "Open", raisedAt: "2026-07-20T08:30:00Z" },
];

export interface QualityCheck {
  id: string;
  orderId: string;
  facility: string;
  service: string;
  area: string;
  result: QualityResult;
  note: string;
}

export const qualityChecks: QualityCheck[] = [
  { id: "QC-901", orderId: "LK-24812", facility: "Industrial Area Plant", service: "Curtains / Upholstery", area: "Sharjah · Al Nahda", result: "Pending", note: "Re-check reported mark before handoff" },
  { id: "QC-902", orderId: "LK-24817", facility: "Marina Hub", service: "Wash & Fold", area: "Dubai · Dubai Marina", result: "Passed", note: "Folded & bagged, ready" },
  { id: "QC-903", orderId: "LK-24811", facility: "Seef Hub", service: "Wash & Fold", area: "Manama · Seef", result: "Passed", note: "OK" },
  { id: "QC-904", orderId: "LK-24816", facility: "Khalidiya Plant", service: "Dry Cleaning", area: "Abu Dhabi · Khalidiya", result: "Pending", note: "Awaiting press completion" },
];

export interface HandoffOrder {
  orderId: string;
  facility: string;
  area: string;
  driver: string | null;
  readyAt: string;
  status: "Ready" | "Driver Assigned" | "Collected";
}

export const deliveryHandoff: HandoffOrder[] = [
  { orderId: "LK-24817", facility: "Marina Hub", area: "Dubai · Dubai Marina", driver: "Bilal K.", readyAt: "2026-07-20T15:00:00Z", status: "Driver Assigned" },
  { orderId: "LK-24811", facility: "Seef Hub", area: "Manama · Seef", driver: null, readyAt: "2026-07-20T12:00:00Z", status: "Ready" },
  { orderId: "LK-24806", facility: "Marina Hub", area: "Dubai · JBR", driver: "Rashid M.", readyAt: "2026-07-19T18:00:00Z", status: "Collected" },
];

export const facilityActivity: OpsActivity[] = [
  { id: "fa1", title: "Order assigned to facility", detail: "LK-24814 → Al Quoz Plant", time: "2026-07-20T07:25:00Z", tone: "info" },
  { id: "fa2", title: "Marked ready for delivery", detail: "LK-24817 · Marina Hub", time: "2026-07-20T09:10:00Z", tone: "success" },
  { id: "fa3", title: "Facility delay flagged", detail: "West Bay Hub · over capacity", time: "2026-07-20T06:05:00Z", tone: "danger" },
  { id: "fa4", title: "Quality check pending", detail: "LK-24812 · curtain re-check", time: "2026-07-20T08:50:00Z", tone: "plum" },
  { id: "fa5", title: "Facility issue raised", detail: "Industrial Area Plant · press unit down", time: "2026-07-20T07:45:00Z", tone: "warning" },
];

export const facilityStatusTone: Record<string, Tone> = {
  Operational: "success",
  "High load": "warning",
  "At capacity": "danger",
  Delayed: "danger",
};

export const facilityOrderStatusTone: Record<string, Tone> = {
  "Awaiting Assignment": "warning",
  "In Cleaning": "info",
  "Quality Check": "plum",
  Delayed: "danger",
  "Ready for Delivery": "success",
};

export const qualityTone: Record<QualityResult, Tone> = {
  Pending: "warning",
  Passed: "success",
  Failed: "danger",
  "N/A": "neutral",
};

export const facilityPriorityTone: Record<string, Tone> = {
  Urgent: "danger",
  High: "warning",
  Standard: "neutral",
};

export const severityTone: Record<string, Tone> = {
  Critical: "danger",
  High: "warning",
  Medium: "info",
};

export const handoffTone: Record<string, Tone> = {
  Ready: "warning",
  "Driver Assigned": "info",
  Collected: "success",
};

/* ================================== DRIVERS ================================= */
/*
 * Pickup & delivery driver operations. Mock-only — no live driver app.
 * PRIVACY: driver-facing rows show customer AREA/CITY only (e.g. "Dubai · Dubai
 * Marina"), never full customer name, phone, email or full street address.
 */

export const driverKpis: KpiStat[] = [
  { label: "Active Drivers", value: "5", delta: 0, tone: "rose", spark: [5, 5, 4, 5, 5, 5, 5], hint: "On roster today" },
  { label: "Drivers Online", value: "3", delta: 20.0, tone: "success", spark: [2, 2, 3, 3, 2, 3, 3] },
  { label: "Pickups Assigned", value: "12", delta: 9.0, tone: "info", spark: [8, 9, 10, 10, 11, 12, 12] },
  { label: "Deliveries Assigned", value: "9", delta: 4.0, tone: "info", spark: [6, 7, 7, 8, 8, 9, 9] },
  { label: "Pickups Completed Today", value: "20", delta: 11.0, tone: "success", spark: [12, 14, 15, 17, 18, 19, 20] },
  { label: "Deliveries Completed Today", value: "17", delta: 6.0, tone: "success", spark: [11, 12, 13, 14, 15, 16, 17] },
  { label: "Delayed Pickups", value: "1", delta: -50.0, tone: "danger", spark: [3, 2, 2, 2, 1, 1, 1] },
  { label: "Delayed Deliveries", value: "1", delta: 0, tone: "danger", spark: [1, 1, 2, 1, 1, 1, 1] },
  { label: "Avg Pickup Time", value: "14m", delta: -7.0, tone: "success", spark: [17, 16, 16, 15, 15, 14, 14], hint: "Assigned → picked up" },
  { label: "Avg Delivery Time", value: "19m", delta: -3.0, tone: "info", spark: [22, 21, 21, 20, 20, 19, 19], hint: "Ready → delivered" },
];

export type DriverStatus = "Online" | "Busy" | "Offline" | "On Pickup" | "On Delivery" | "Delayed";

export interface Driver {
  name: string;
  status: DriverStatus;
  zone: string; // display area, e.g. "Dubai Marina"
  city: string; // for global filters
  assignedOrders: number;
  completedToday: number;
  delayedJobs: number;
  rating: number; // driver PPI / rating out of 5
  ppiScore: number;
  lastActive: string;
}

export const drivers: Driver[] = [
  { name: "Ahmed Khan", status: "Online", zone: "Dubai Marina", city: "Dubai", assignedOrders: 4, completedToday: 6, delayedJobs: 0, rating: 4.9, ppiScore: 96, lastActive: "2026-07-20T09:38:00Z" },
  { name: "Fatima Noor", status: "Online", zone: "Abu Dhabi · Corniche", city: "Abu Dhabi", assignedOrders: 3, completedToday: 5, delayedJobs: 0, rating: 4.8, ppiScore: 94, lastActive: "2026-07-20T09:35:00Z" },
  { name: "Omar Saeed", status: "Busy", zone: "Business Bay", city: "Dubai", assignedOrders: 5, completedToday: 4, delayedJobs: 1, rating: 4.6, ppiScore: 89, lastActive: "2026-07-20T09:40:00Z" },
  { name: "Rakesh Kumar", status: "Offline", zone: "Sharjah · Al Nahda", city: "Sharjah", assignedOrders: 0, completedToday: 2, delayedJobs: 0, rating: 4.5, ppiScore: 85, lastActive: "2026-07-20T07:10:00Z" },
  { name: "Bilal Ansari", status: "Online", zone: "Jumeirah", city: "Dubai", assignedOrders: 2, completedToday: 3, delayedJobs: 0, rating: 4.7, ppiScore: 92, lastActive: "2026-07-20T09:30:00Z" },
];

export type PickupStatus =
  | "Awaiting Driver"
  | "Driver Assigned"
  | "En Route to Customer"
  | "Picked Up"
  | "Delayed"
  | "Failed Pickup";

export interface PickupJob {
  orderId: string;
  area: string; // customer AREA/CITY only
  service: string;
  pickupSlot: string;
  driver: string | null;
  status: PickupStatus;
  priority: "Urgent" | "High" | "Standard";
  notes: string;
}

export const pickupQueue: PickupJob[] = [
  { orderId: "LK-24817", area: "Dubai · Dubai Marina", service: "Wash & Fold", pickupSlot: "Today 15:00–17:00", driver: "Ahmed Khan", status: "Driver Assigned", priority: "Standard", notes: "Building 2, concierge hold" },
  { orderId: "LK-24818", area: "Dubai · JLT", service: "Blankets / Duvets", pickupSlot: "Today 16:00–18:00", driver: null, status: "Awaiting Driver", priority: "High", notes: "2 duvets, bulky" },
  { orderId: "LK-24810", area: "Kuwait City · Salmiya", service: "Dry Cleaning", pickupSlot: "Tomorrow 13:00–15:00", driver: null, status: "Awaiting Driver", priority: "Standard", notes: "Reschedule confirmed" },
  { orderId: "LK-24814", area: "Dubai · Business Bay", service: "Business Laundry", pickupSlot: "Today 12:00–14:00", driver: "Omar Saeed", status: "En Route to Customer", priority: "High", notes: "Reception pickup" },
  { orderId: "LK-24820", area: "Abu Dhabi · Khalidiya", service: "Wash & Fold", pickupSlot: "Today 14:00–16:00", driver: "Fatima Noor", status: "Picked Up", priority: "Standard", notes: "Collected, en route to plant" },
  { orderId: "LK-24821", area: "Dubai · Jumeirah", service: "Ironing / Pressing", pickupSlot: "Today 17:00–19:00", driver: "Bilal Ansari", status: "Driver Assigned", priority: "Standard", notes: "" },
  { orderId: "LK-24808", area: "Doha · West Bay", service: "Business Laundry", pickupSlot: "Today 10:00–12:00", driver: null, status: "Delayed", priority: "Urgent", notes: "Driver not reachable — reassign" },
];

export type DeliveryStatus =
  | "Awaiting Delivery"
  | "Driver Assigned"
  | "En Route to Customer"
  | "Delivered"
  | "Delayed"
  | "Failed Delivery";

export interface DeliveryJob {
  orderId: string;
  area: string;
  service: string;
  deliverySlot: string;
  driver: string | null;
  facility: string;
  status: DeliveryStatus;
  paymentStatus: string; // mirrors payment status label
}

export const deliveryQueue: DeliveryJob[] = [
  { orderId: "LK-24817", area: "Dubai · Dubai Marina", service: "Wash & Fold", deliverySlot: "Today 18:00–20:00", driver: "Ahmed Khan", facility: "Marina Hub", status: "Driver Assigned", paymentStatus: "Pending" },
  { orderId: "LK-24811", area: "Manama · Seef", service: "Wash & Fold", deliverySlot: "Today 13:00–15:00", driver: null, facility: "Seef Hub", status: "Awaiting Delivery", paymentStatus: "Paid" },
  { orderId: "LK-24806", area: "Dubai · JBR", service: "Dry Cleaning", deliverySlot: "Today 11:00–12:00", driver: "Bilal Ansari", facility: "Marina Hub", status: "Delivered", paymentStatus: "Paid" },
  { orderId: "LK-24816", area: "Abu Dhabi · Khalidiya", service: "Dry Cleaning", deliverySlot: "Tomorrow 10:00–12:00", driver: "Fatima Noor", facility: "Khalidiya Plant", status: "Driver Assigned", paymentStatus: "Pending" },
  { orderId: "LK-24809", area: "Dubai · Business Bay", service: "Wash & Fold", deliverySlot: "Today 19:00–21:00", driver: "Omar Saeed", facility: "Al Quoz Plant", status: "En Route to Customer", paymentStatus: "Pending" },
  { orderId: "LK-24805", area: "Sharjah · Al Nahda", service: "Blankets / Duvets", deliverySlot: "Today 20:00–22:00", driver: null, facility: "Industrial Area Plant", status: "Delayed", paymentStatus: "Pending" },
];

export interface DriverPerformance {
  driver: string;
  city: string; // driver home city — for global geo filters
  completedToday: number;
  onTimePct: number;
  avgPickup: string;
  avgDelivery: string;
  rating: number;
  ppiScore: number;
}

export const driverPerformance: DriverPerformance[] = [
  { driver: "Ahmed Khan", city: "Dubai", completedToday: 6, onTimePct: 98, avgPickup: "12m", avgDelivery: "17m", rating: 4.9, ppiScore: 96 },
  { driver: "Fatima Noor", city: "Abu Dhabi", completedToday: 5, onTimePct: 96, avgPickup: "13m", avgDelivery: "18m", rating: 4.8, ppiScore: 94 },
  { driver: "Bilal Ansari", city: "Dubai", completedToday: 3, onTimePct: 94, avgPickup: "15m", avgDelivery: "19m", rating: 4.7, ppiScore: 92 },
  { driver: "Omar Saeed", city: "Dubai", completedToday: 4, onTimePct: 87, avgPickup: "18m", avgDelivery: "23m", rating: 4.6, ppiScore: 89 },
  { driver: "Rakesh Kumar", city: "Sharjah", completedToday: 2, onTimePct: 85, avgPickup: "19m", avgDelivery: "24m", rating: 4.5, ppiScore: 85 },
];

export interface DriverIssue {
  id: string;
  driver: string;
  orderId: string;
  city: string; // customer city (area-level) — for global geo filters
  issueType: string;
  priority: "Urgent" | "High" | "Medium" | "Low";
  status: "Open" | "Investigating" | "Resolved";
  reportedAt: string;
  actionNeeded: string;
}

export const driverIssues: DriverIssue[] = [
  { id: "DI-401", driver: "Omar Saeed", orderId: "LK-24814", city: "Dubai", issueType: "Pickup delayed", priority: "High", status: "Open", reportedAt: "2026-07-20T09:10:00Z", actionNeeded: "Extend slot or reassign" },
  { id: "DI-402", driver: "Unassigned", orderId: "LK-24808", city: "Doha", issueType: "Driver not reachable", priority: "Urgent", status: "Investigating", reportedAt: "2026-07-20T08:50:00Z", actionNeeded: "Call driver / reassign pickup" },
  { id: "DI-403", driver: "Fatima Noor", orderId: "LK-24816", city: "Abu Dhabi", issueType: "Customer not available", priority: "Medium", status: "Open", reportedAt: "2026-07-20T09:20:00Z", actionNeeded: "Contact customer, reschedule" },
  { id: "DI-404", driver: "Ahmed Khan", orderId: "LK-24817", city: "Dubai", issueType: "Location unclear", priority: "Medium", status: "Open", reportedAt: "2026-07-20T09:32:00Z", actionNeeded: "Share map pin with driver" },
  { id: "DI-405", driver: "Unassigned", orderId: "LK-24805", city: "Sharjah", issueType: "Payment collection issue", priority: "High", status: "Open", reportedAt: "2026-07-20T09:05:00Z", actionNeeded: "POD not collected — send to Payments" },
  { id: "DI-406", driver: "Bilal Ansari", orderId: "LK-24806", city: "Dubai", issueType: "Item photo missing", priority: "Low", status: "Resolved", reportedAt: "2026-07-20T07:40:00Z", actionNeeded: "—" },
];

export const driverActivity: OpsActivity[] = [
  { id: "da1", title: "Pickup completed", detail: "LK-24820 · Fatima Noor · Khalidiya", time: "2026-07-20T09:30:00Z", tone: "success" },
  { id: "da2", title: "Delivery en route", detail: "LK-24809 · Omar Saeed · Business Bay", time: "2026-07-20T09:25:00Z", tone: "plum" },
  { id: "da3", title: "Delayed pickup flagged", detail: "LK-24808 · driver not reachable", time: "2026-07-20T08:50:00Z", tone: "danger" },
  { id: "da4", title: "Driver went offline", detail: "Rakesh Kumar · Sharjah", time: "2026-07-20T07:10:00Z", tone: "neutral" },
  { id: "da5", title: "Payment collection issue", detail: "LK-24805 · POD not collected", time: "2026-07-20T09:05:00Z", tone: "warning" },
];

export const driverStatusTone: Record<string, Tone> = {
  Online: "success",
  Busy: "warning",
  Offline: "neutral",
  "On Pickup": "info",
  "On Delivery": "info",
  Delayed: "danger",
};

export const pickupStatusTone: Record<string, Tone> = {
  "Awaiting Driver": "warning",
  "Driver Assigned": "info",
  "En Route to Customer": "plum",
  "Picked Up": "success",
  Delayed: "danger",
  "Failed Pickup": "danger",
};

export const deliveryStatusTone: Record<string, Tone> = {
  "Awaiting Delivery": "warning",
  "Driver Assigned": "info",
  "En Route to Customer": "plum",
  Delivered: "success",
  Delayed: "danger",
  "Failed Delivery": "danger",
};

/* ==================== CUSTOMER CHARGES / PAYMENTS ==================== */
/*
 * Operational, customer-level payment visibility — NOT the executive Finance
 * dashboard. Mock-only: no live Stripe, no gateway, no real charges/refunds.
 * PRIVACY: no card numbers, CVV, bank details or unmasked phone. Amount,
 * method label, status, order ID and area/city only. Refunds & adjustments
 * always require human approval.
 */

export const paymentKpis: KpiStat[] = [
  { label: "Total Customer Charges", value: "AED 18.4k", delta: 7.4, tone: "rose", spark: [14, 15, 15, 16, 17, 18, 18], hint: "Open + settled this period" },
  { label: "Paid Orders", value: "132", delta: 5.2, tone: "success", spark: [110, 116, 120, 124, 128, 130, 132] },
  { label: "Pending Payments", value: "14", delta: 3.0, tone: "warning", spark: [9, 10, 11, 12, 13, 13, 14] },
  { label: "Failed Payments", value: "3", delta: 1.0, tone: "danger", spark: [1, 2, 2, 2, 3, 2, 3] },
  { label: "Refund Requests", value: "5", delta: 2.0, tone: "plum", spark: [2, 3, 3, 4, 4, 5, 5] },
  { label: "Adjustments Pending", value: "3", delta: 1.0, tone: "warning", spark: [1, 1, 2, 2, 2, 3, 3] },
  { label: "Cash / Pay on Delivery", value: "46", delta: -4.0, tone: "info", spark: [52, 50, 49, 48, 47, 46, 46] },
  { label: "Card / Online Payments", value: "88", delta: 8.0, tone: "info", spark: [72, 76, 79, 82, 85, 87, 88] },
  { label: "Invoice Payments", value: "6", delta: 0, tone: "info", spark: [5, 6, 6, 5, 6, 6, 6] },
  { label: "Payment Issues Open", value: "4", delta: 1.0, tone: "danger", spark: [2, 2, 3, 3, 3, 4, 4] },
];

export type PaymentMethod = "Pay on Delivery" | "Card" | "Invoice" | "Online";

export type PaymentState =
  | "Paid"
  | "Pending"
  | "Failed"
  | "Refunded"
  | "Refund Requested"
  | "Adjustment Pending"
  | "Invoice Sent"
  | "Overdue";

export interface PaymentRecord {
  orderId: string;
  customer: string;
  service: string;
  amount: number;
  method: PaymentMethod;
  status: PaymentState;
  chargeStatus: "Charged" | "Not Charged" | "Authorized" | "Refunded" | "Failed" | "Invoice Sent";
  area: string;
  channel: string;
  createdAt: string;
}

export const paymentRecords: PaymentRecord[] = [
  { orderId: "LK-AE-1024", customer: "Yusuf Ahmed", service: "Wash & Fold", amount: 145, method: "Pay on Delivery", status: "Pending", chargeStatus: "Not Charged", area: "Dubai · Dubai Marina", channel: "WhatsApp", createdAt: "2026-07-20T08:10:00Z" },
  { orderId: "LK-AE-1025", customer: "Noor Salem", service: "Dry Cleaning", amount: 90, method: "Card", status: "Failed", chargeStatus: "Failed", area: "Dubai · JLT", channel: "App", createdAt: "2026-07-20T08:25:00Z" },
  { orderId: "LK-AE-1026", customer: "Grand Bay Hotel", service: "Business Laundry", amount: 2800, method: "Invoice", status: "Invoice Sent", chargeStatus: "Invoice Sent", area: "Doha · West Bay", channel: "B2B", createdAt: "2026-07-19T14:00:00Z" },
  { orderId: "LK-AE-1027", customer: "Mariam Khalid", service: "Ironing / Pressing", amount: 60, method: "Card", status: "Paid", chargeStatus: "Charged", area: "Abu Dhabi · Khalidiya", channel: "Website", createdAt: "2026-07-20T07:50:00Z" },
  { orderId: "LK-AE-2031", customer: "Hamad Al Otaibi", service: "Wash & Fold", amount: 120, method: "Pay on Delivery", status: "Pending", chargeStatus: "Not Charged", area: "Sharjah · Al Nahda", channel: "WhatsApp", createdAt: "2026-07-20T09:15:00Z" },
  { orderId: "LK-24817", customer: "Aisha Rahman", service: "Wash & Fold", amount: 85, method: "Card", status: "Paid", chargeStatus: "Charged", area: "Dubai · Dubai Marina", channel: "WhatsApp", createdAt: "2026-07-20T09:20:00Z" },
  { orderId: "LK-24815", customer: "Fatima Al-Suwaidi", service: "Blankets / Duvets", amount: 150, method: "Card", status: "Refund Requested", chargeStatus: "Charged", area: "Doha · West Bay", channel: "App", createdAt: "2026-07-20T08:40:00Z" },
];

export interface PendingPayment {
  orderId: string;
  customer: string;
  amountDue: number;
  method: PaymentMethod;
  dueStatus: string;
  deliveryStatus: string;
  followupNeeded: boolean;
  area: string;
}

export const pendingPayments: PendingPayment[] = [
  { orderId: "LK-AE-1024", customer: "Yusuf Ahmed", amountDue: 145, method: "Pay on Delivery", dueStatus: "Due on Delivery", deliveryStatus: "Out for Delivery", followupNeeded: true, area: "Dubai · Dubai Marina" },
  { orderId: "LK-AE-1026", customer: "Grand Bay Hotel", amountDue: 2800, method: "Invoice", dueStatus: "Due in 12 days", deliveryStatus: "Delivered", followupNeeded: false, area: "Doha · West Bay" },
  { orderId: "LK-AE-2031", customer: "Hamad Al Otaibi", amountDue: 120, method: "Pay on Delivery", dueStatus: "Due on Delivery", deliveryStatus: "Pickup Scheduled", followupNeeded: true, area: "Sharjah · Al Nahda" },
  { orderId: "LK-AE-1025", customer: "Noor Salem", amountDue: 90, method: "Card", dueStatus: "Retry needed", deliveryStatus: "Awaiting Payment", followupNeeded: true, area: "Dubai · JLT" },
  { orderId: "LK-24808", customer: "West Bay Hotel", amountDue: 3200, method: "Invoice", dueStatus: "Overdue 3 days", deliveryStatus: "Delivered", followupNeeded: true, area: "Doha · West Bay" },
];

export interface RefundRequest {
  id: string;
  orderId: string;
  customer: string;
  amount: number;
  reason: string;
  orderStatus: string;
  paymentStatus: string;
  urgency: "Urgent" | "High" | "Medium" | "Low";
  approvalStatus: "Approval Required" | "Pending Review" | "Approved" | "Rejected";
  area: string;
}

export const refundRequests: RefundRequest[] = [
  { id: "RF-6001", orderId: "LK-24815", customer: "Fatima Al-Suwaidi", amount: 150, reason: "Customer wants refund", orderStatus: "Cancelled", paymentStatus: "Refund Requested", urgency: "High", approvalStatus: "Approval Required", area: "Doha · West Bay" },
  { id: "RF-6002", orderId: "LK-24812", customer: "Hassan Ali", amount: 220, reason: "Damaged item refund review", orderStatus: "Delivered", paymentStatus: "Paid", urgency: "Urgent", approvalStatus: "Approval Required", area: "Sharjah · Al Nahda" },
  { id: "RF-6003", orderId: "LK-24806", customer: "Rashid Omar", amount: 60, reason: "Missing item refund review", orderStatus: "Delivered", paymentStatus: "Paid", urgency: "Medium", approvalStatus: "Pending Review", area: "Dubai · JBR" },
  { id: "RF-6004", orderId: "LK-AE-1027", customer: "Mariam Khalid", amount: 60, reason: "Duplicate payment refund review", orderStatus: "Delivered", paymentStatus: "Paid", urgency: "Low", approvalStatus: "Pending Review", area: "Abu Dhabi · Khalidiya" },
  { id: "RF-6005", orderId: "LK-24808", customer: "Grand Bay Hotel", amount: 300, reason: "Late delivery compensation request", orderStatus: "Delivered", paymentStatus: "Paid", urgency: "Medium", approvalStatus: "Approval Required", area: "Doha · West Bay" },
];

export interface Adjustment {
  orderId: string;
  customer: string;
  originalAmount: number;
  extraCharge: number;
  reason: string;
  approvalStatus: "Approval Required" | "Approved" | "Rejected";
  finalAmount: number;
  area: string;
  service: string;
}

export const adjustments: Adjustment[] = [
  { orderId: "LK-24814", customer: "Business Bay Offices", originalAmount: 900, extraCharge: 120, reason: "Extra 40 shirts added at pickup", approvalStatus: "Approval Required", finalAmount: 1020, area: "Dubai · Business Bay", service: "Business Laundry" },
  { orderId: "LK-24818", customer: "Sara Juma", originalAmount: 140, extraCharge: 35, reason: "Express turnaround surcharge", approvalStatus: "Approval Required", finalAmount: 175, area: "Dubai · JLT", service: "Blankets / Duvets" },
  { orderId: "LK-24816", customer: "Omar Haddad", originalAmount: 90, extraCharge: 25, reason: "Additional stain treatment", approvalStatus: "Approved", finalAmount: 115, area: "Abu Dhabi · Khalidiya", service: "Dry Cleaning" },
];

export interface PaymentIssue {
  id: string;
  orderId: string;
  customer: string;
  issueType: string;
  amount: number;
  method: PaymentMethod;
  priority: "Urgent" | "High" | "Medium" | "Low";
  assignedTeam: string;
  status: "Open" | "Investigating" | "Resolved";
  area: string;
}

export const paymentIssues: PaymentIssue[] = [
  { id: "PI-801", orderId: "LK-AE-1025", customer: "Noor Salem", issueType: "Failed card charge", amount: 90, method: "Card", priority: "High", assignedTeam: "Payments", status: "Open", area: "Dubai · JLT" },
  { id: "PI-802", orderId: "LK-AE-1024", customer: "Yusuf Ahmed", issueType: "Cash not collected", amount: 145, method: "Pay on Delivery", priority: "High", assignedTeam: "Drivers + Payments", status: "Open", area: "Dubai · Dubai Marina" },
  { id: "PI-803", orderId: "LK-AE-1027", customer: "Mariam Khalid", issueType: "Duplicate charge", amount: 60, method: "Card", priority: "Medium", assignedTeam: "Payments + Finance", status: "Investigating", area: "Abu Dhabi · Khalidiya" },
  { id: "PI-804", orderId: "LK-24808", customer: "West Bay Hotel", issueType: "B2B invoice overdue", amount: 3200, method: "Invoice", priority: "Medium", assignedTeam: "Payments + Sales", status: "Open", area: "Doha · West Bay" },
];

export interface Invoice {
  id: string;
  businessCustomer: string;
  service: string;
  amount: number;
  billingPeriod: string;
  status: "Draft" | "Sent" | "Paid" | "Overdue";
  dueDate: string;
  city: string; // billing city — for global geo filters
  channel: string; // B2B invoices
}

export const invoices: Invoice[] = [
  { id: "INV-2201", businessCustomer: "Grand Bay Hotel", service: "Business Laundry", amount: 2800, billingPeriod: "Jul 2026", status: "Sent", dueDate: "2026-08-01", city: "Doha", channel: "B2B" },
  { id: "INV-2202", businessCustomer: "West Bay Hotel", service: "Business Laundry", amount: 3200, billingPeriod: "Jun 2026", status: "Overdue", dueDate: "2026-07-15", city: "Doha", channel: "B2B" },
  { id: "INV-2203", businessCustomer: "Business Bay Offices", service: "Wash & Fold", amount: 1450, billingPeriod: "Jul 2026", status: "Paid", dueDate: "2026-07-10", city: "Dubai", channel: "B2B" },
  { id: "INV-2204", businessCustomer: "Marina Residences", service: "Curtains / Upholstery", amount: 980, billingPeriod: "Jul 2026", status: "Draft", dueDate: "2026-08-05", city: "Dubai", channel: "B2B" },
];

export const paymentActivity: OpsActivity[] = [
  { id: "pa1", title: "Refund review requested", detail: "LK-24812 · damaged item · AED 220", time: "2026-07-20T09:18:00Z", tone: "plum" },
  { id: "pa2", title: "Card payment failed", detail: "LK-AE-1025 · Noor Salem · AED 90", time: "2026-07-20T08:25:00Z", tone: "danger" },
  { id: "pa3", title: "POD pending on delivery", detail: "LK-AE-1024 · AED 145 · Dubai Marina", time: "2026-07-20T08:10:00Z", tone: "warning" },
  { id: "pa4", title: "Adjustment awaiting approval", detail: "LK-24814 · +AED 120 extra items", time: "2026-07-20T07:55:00Z", tone: "warning" },
  { id: "pa5", title: "B2B invoice overdue", detail: "INV-2202 · West Bay Hotel · AED 3,200", time: "2026-07-20T06:30:00Z", tone: "danger" },
];

export const paymentStatusTone: Record<string, Tone> = {
  Paid: "success",
  Pending: "warning",
  Failed: "danger",
  Refunded: "neutral",
  "Refund Requested": "plum",
  "Adjustment Pending": "warning",
  "Invoice Sent": "info",
  Overdue: "danger",
};

export const chargeStatusTone: Record<string, Tone> = {
  Charged: "success",
  "Not Charged": "neutral",
  Authorized: "info",
  Refunded: "neutral",
  Failed: "danger",
  "Invoice Sent": "info",
};

export const approvalStatusTone: Record<string, Tone> = {
  "Approval Required": "warning",
  "Pending Review": "plum",
  Approved: "success",
  Rejected: "danger",
};

export const invoiceStatusTone: Record<string, Tone> = {
  Draft: "neutral",
  Sent: "info",
  Paid: "success",
  Overdue: "danger",
};

/** Due-status colouring: overdue/retry read as danger, everything else warning. */
export function dueStatusTone(status: string): Tone {
  return /overdue|retry|failed/i.test(status) ? "danger" : "warning";
}

/* ============================== CUSTOMER ORDERS ============================== */
/*
 * The dedicated order-management center (distinct from Customer Facing support).
 * Reads the shared `orders` mock (mock-data.ts) for the order rows; the helpers
 * below add order-center context (next step, SLA, rating, issues).
 */

export const customerOrdersKpis: KpiStat[] = [
  { label: "Total Active Orders", value: "82", delta: 7.4, tone: "rose", spark: [64, 68, 71, 74, 77, 80, 82], hint: "Not delivered or cancelled" },
  { label: "New Orders", value: "14", delta: 12.0, tone: "info", spark: [8, 9, 10, 11, 12, 13, 14] },
  { label: "Pickup Scheduled", value: "19", delta: 3.0, tone: "info", spark: [14, 15, 16, 17, 18, 18, 19] },
  { label: "In Cleaning", value: "28", delta: 5.0, tone: "warning", spark: [22, 23, 24, 25, 26, 27, 28] },
  { label: "Ready for Delivery", value: "11", delta: 8.0, tone: "plum", spark: [6, 7, 8, 9, 10, 10, 11] },
  { label: "Out for Delivery", value: "10", delta: 4.0, tone: "rose", spark: [6, 7, 7, 8, 9, 9, 10] },
  { label: "Completed Today", value: "31", delta: 9.0, tone: "success", spark: [20, 23, 25, 27, 28, 30, 31] },
  { label: "Cancelled Orders", value: "3", delta: -1.0, tone: "neutral", spark: [5, 4, 4, 3, 3, 3, 3] },
  { label: "Orders With Issues", value: "5", delta: 1.0, tone: "danger", spark: [3, 3, 4, 4, 4, 5, 5] },
  { label: "Payment Pending", value: "7", delta: -2.0, tone: "warning", spark: [10, 9, 9, 8, 8, 7, 7] },
];

/** Terminal statuses that mean an order is no longer "active". */
export const ACTIVE_EXCLUDED = new Set(["Delivered", "Cancelled"]);

/** Order status → the next operational step (order-center guidance). */
export const nextStepByStatus: Record<string, string> = {
  New: "Confirm details & schedule pickup",
  "Pickup Scheduled": "Assign a driver for pickup",
  "Driver Assigned": "Driver en route to pickup",
  "Picked Up": "Deliver to facility & start cleaning",
  "In Cleaning": "Complete cleaning & quality check",
  "Ready for Delivery": "Assign a driver for delivery",
  "Out for Delivery": "Deliver & confirm with customer",
  Delivered: "Order complete",
  Cancelled: "No further action",
  "Concern Raised": "Resolve customer concern",
};

/** SLA read-out per status — mock, deterministic. */
export function orderSla(status: string): { label: string; tone: Tone } {
  if (status === "Concern Raised") return { label: "At risk", tone: "danger" };
  if (status === "Delivered" || status === "Cancelled") return { label: "Closed", tone: "neutral" };
  if (status === "In Cleaning" || status === "Out for Delivery") return { label: "On track", tone: "success" };
  if (status === "New" || status === "Pickup Scheduled") return { label: "Due soon", tone: "warning" };
  return { label: "On track", tone: "success" };
}

/** Deterministic mock rating for delivered orders (order id → stars). */
export const orderRatings: Record<string, number> = {
  "LK-24813": 5,
  "LK-24806": 4,
};

export interface OrderIssue {
  id: string;
  orderId: string;
  customer: string;
  city: string; // order city — for global geo filters
  issueType: "Damage" | "Delay" | "Lost Item" | "Quality" | "Billing";
  priority: "Urgent" | "High" | "Medium" | "Low";
  assignedTeam: string;
  status: "Open" | "Investigating" | "Resolved";
  lastUpdate: string;
}

export const orderIssues: OrderIssue[] = [
  { id: "OI-8801", orderId: "LK-24812", customer: "Hassan Ali", city: "Sharjah", issueType: "Damage", priority: "High", assignedTeam: "Quality — Huda", status: "Investigating", lastUpdate: "2026-07-20T09:22:00Z" },
  { id: "OI-8802", orderId: "LK-24810", customer: "Khalid Nasser", city: "Kuwait City", issueType: "Delay", priority: "Medium", assignedTeam: "Ops — Faris", status: "Open", lastUpdate: "2026-07-20T09:05:00Z" },
  { id: "OI-8803", orderId: "LK-24808", customer: "Grand Bay Hotel (B2B)", city: "Doha", issueType: "Billing", priority: "Urgent", assignedTeam: "Finance — Dana", status: "Open", lastUpdate: "2026-07-20T08:40:00Z" },
  { id: "OI-8804", orderId: "LK-24815", customer: "Fatima Al-Suwaidi", city: "Doha", issueType: "Lost Item", priority: "High", assignedTeam: "Ops — Faris", status: "Investigating", lastUpdate: "2026-07-20T08:10:00Z" },
  { id: "OI-8805", orderId: "LK-24816", customer: "Omar Haddad", city: "Abu Dhabi", issueType: "Quality", priority: "Low", assignedTeam: "Quality — Huda", status: "Resolved", lastUpdate: "2026-07-19T18:30:00Z" },
];

export const orderIssueStatusTone: Record<OrderIssue["status"], Tone> = {
  Open: "warning",
  Investigating: "info",
  Resolved: "success",
};

export interface OrderCenterActivity {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
}

export const orderCenterActivity: OrderCenterActivity[] = [
  { id: "oc1", title: "New order created", detail: "LK-24810 · Dry Cleaning · Kuwait City", time: "2026-07-20T09:45:00Z", tone: "info" },
  { id: "oc2", title: "Order out for delivery", detail: "LK-24817 · Wash & Fold · Dubai", time: "2026-07-20T09:20:00Z", tone: "rose" },
  { id: "oc3", title: "Concern raised on order", detail: "LK-24812 · curtain returned with a mark", time: "2026-07-19T09:30:00Z", tone: "danger" },
  { id: "oc4", title: "Order delivered", detail: "LK-24806 · Ironing · Dubai · rated 4★", time: "2026-07-19T10:20:00Z", tone: "success" },
  { id: "oc5", title: "Order change requested", detail: "LK-24810 · reschedule pickup", time: "2026-07-20T09:05:00Z", tone: "plum" },
];
