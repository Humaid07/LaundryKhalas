/**
 * Finance & Compliance mock data — extends the existing finance analytics
 * (mock-data.ts) with operational compliance & risk oversight. Mock-only.
 *
 * PRIVACY: no card numbers, no bank details, no full customer PII. Refunds and
 * adjustments require human approval. Documents are status-only.
 */
import type { KpiStat, Tone, TimeSeriesPoint, CostLine } from "./types";
import { paymentRecords, invoices, type PaymentRecord, type Invoice } from "./operations-data";

const spark = (n: number[]) => n;

/* ------------------------------ Extra finance KPI --------------------------- */

export const driverCostKpi: KpiStat = {
  label: "Driver Cost",
  value: "AED 118K",
  delta: 4.2,
  tone: "rose",
  spark: spark([104, 108, 110, 112, 114, 116, 118]),
};

/* ------------------------------ Compliance KPIs ----------------------------- */

export const complianceKpis: KpiStat[] = [
  { label: "Compliance Reviews Pending", value: "6", delta: 2.0, tone: "warning", spark: spark([3, 4, 4, 5, 5, 6, 6]) },
  { label: "Documents Expiring Soon", value: "4", delta: 1.0, tone: "danger", spark: spark([1, 2, 2, 3, 3, 4, 4]) },
  { label: "Refund Approvals Pending", value: "5", delta: -1.0, tone: "warning", spark: spark([7, 7, 6, 6, 6, 5, 5]) },
  { label: "Payment Issues Open", value: "8", delta: 3.0, tone: "danger", spark: spark([4, 5, 6, 6, 7, 8, 8]) },
  { label: "Partner Compliance Pass Rate", value: "82%", delta: 2.4, tone: "success", spark: spark([76, 77, 78, 79, 80, 81, 82]) },
  { label: "Facility Compliance Issues", value: "3", delta: 0, tone: "warning", spark: spark([4, 3, 3, 4, 3, 3, 3]) },
  { label: "Driver Compliance Issues", value: "5", delta: 1.0, tone: "warning", spark: spark([3, 4, 4, 4, 5, 5, 5]) },
  { label: "Audit Flags", value: "7", delta: 2.0, tone: "danger", spark: spark([4, 5, 5, 6, 6, 7, 7]) },
  { label: "High-Risk Transactions", value: "2", delta: 0, tone: "danger", spark: spark([3, 2, 2, 3, 2, 2, 2]) },
  { label: "Unresolved Disputes", value: "3", delta: -1.0, tone: "warning", spark: spark([5, 5, 4, 4, 4, 3, 3]) },
];

/* ---------------------------- Extended cost breakdown ----------------------- */

export const extendedCostBreakdown: CostLine[] = [
  { category: "Facility Cost", amount: 162000, pctOfCost: 36.9, delta: 5.0, note: "Plant labor, utilities, consumables", tone: "info" },
  { category: "Driver Cost", amount: 118000, pctOfCost: 26.9, delta: 4.2, note: "Pickup & delivery fleet", tone: "rose" },
  { category: "Marketing Cost", amount: 54000, pctOfCost: 12.3, delta: 9.0, note: "Paid social, campaigns, creative", tone: "warning" },
  { category: "Payment Gateway Cost", amount: 24400, pctOfCost: 5.6, delta: 2.0, note: "Gateway & processing fees", tone: "neutral" },
  { category: "Tech Cost", amount: 21000, pctOfCost: 4.8, delta: 4.0, note: "Hosting, tools, integrations", tone: "info" },
  { category: "Refund / Compensation Cost", amount: 11600, pctOfCost: 2.6, delta: 8.0, note: "Approved refunds & goodwill", tone: "plum" },
  { category: "Damage Cost", amount: 8400, pctOfCost: 1.9, delta: 14.0, note: "Reprocessing & claims", tone: "danger" },
  { category: "AI / LLM Cost", amount: 3200, pctOfCost: 0.7, delta: 26.0, note: "Agent inference (estimate)", tone: "plum" },
];

/* ------------------------------ Customer payments --------------------------- */

export interface PaymentStatusRow {
  status: "Paid" | "Pending" | "Failed" | "Refund Requested" | "Invoice Sent" | "Overdue";
  count: number;
  amount: number;
  tone: Tone;
}

export const paymentStatusRows: PaymentStatusRow[] = [
  { status: "Paid", count: 1284, amount: 226100, tone: "success" },
  { status: "Pending", count: 96, amount: 16880, tone: "warning" },
  { status: "Failed", count: 21, amount: 3690, tone: "danger" },
  { status: "Refund Requested", count: 12, amount: 2140, tone: "plum" },
  { status: "Invoice Sent", count: 34, amount: 41200, tone: "info" },
  { status: "Overdue", count: 9, amount: 13750, tone: "danger" },
];

/* ---------------------------- Refunds & adjustments ------------------------- */

export interface RefundAdjustment {
  id: string;
  type: "Refund" | "Adjustment";
  orderRef: string;
  reason: string;
  amount: number;
  approval: "Approval Required" | "Pending Review" | "Approved" | "Declined";
  reviewer: string;
  /** Geo signal for the global filters (city → market → region). */
  city: string;
  createdAt: string;
}

export const refundsAdjustments: RefundAdjustment[] = [
  { id: "RF-9001", type: "Refund", orderRef: "LK-24815", reason: "Item damaged in cleaning", amount: 120, approval: "Approval Required", reviewer: "Dana Aziz (Finance)", city: "Dubai", createdAt: "2026-07-20T09:05:00Z" },
  { id: "RF-9002", type: "Refund", orderRef: "LK-24790", reason: "Late delivery goodwill", amount: 45, approval: "Pending Review", reviewer: "Dana Aziz (Finance)", city: "Abu Dhabi", createdAt: "2026-07-20T08:30:00Z" },
  { id: "AJ-9003", type: "Adjustment", orderRef: "LK-24812", reason: "Extra duvet added post-quote", amount: 60, approval: "Approval Required", reviewer: "Faris Al-Rashid (Ops)", city: "Sharjah", createdAt: "2026-07-19T15:00:00Z" },
  { id: "RF-9004", type: "Refund", orderRef: "LK-24777", reason: "Duplicate charge reversal", amount: 176, approval: "Approved", reviewer: "Dana Aziz (Finance)", city: "Doha", createdAt: "2026-07-20T09:10:00Z" },
  { id: "AJ-9005", type: "Adjustment", orderRef: "LK-24801", reason: "Express turnaround surcharge", amount: 35, approval: "Approved", reviewer: "Faris Al-Rashid (Ops)", city: "Dubai", createdAt: "2026-07-18T11:00:00Z" },
  { id: "RF-9006", type: "Refund", orderRef: "LK-24765", reason: "Service not delivered", amount: 90, approval: "Declined", reviewer: "Dana Aziz (Finance)", city: "Riyadh", createdAt: "2026-07-17T14:00:00Z" },
];

export const approvalTone: Record<RefundAdjustment["approval"], Tone> = {
  "Approval Required": "rose",
  "Pending Review": "warning",
  Approved: "success",
  Declined: "neutral",
};

/* --------------------------- Partner / facility compliance ------------------ */

export interface FacilityCompliance {
  name: string;
  city: string;
  license: "Valid" | "Expiring" | "Expired";
  agreement: "Signed" | "Pending" | "N/A";
  qualityChecklist: "Passed" | "Partial" | "Failed";
  documents: "Complete" | "Missing";
  score: number;
  risk: "Low" | "Medium" | "High";
}

export const facilityCompliance: FacilityCompliance[] = [
  { name: "Al Quoz Premium Cleaners", city: "Dubai", license: "Valid", agreement: "Signed", qualityChecklist: "Passed", documents: "Complete", score: 94, risk: "Low" },
  { name: "Doha West Bay Facility", city: "Doha", license: "Expiring", agreement: "Signed", qualityChecklist: "Partial", documents: "Missing", score: 72, risk: "Medium" },
  { name: "Riyadh Central Plant", city: "Riyadh", license: "Valid", agreement: "Pending", qualityChecklist: "Passed", documents: "Complete", score: 81, risk: "Low" },
  { name: "Sharjah Industrial Cleaners", city: "Sharjah", license: "Expired", agreement: "N/A", qualityChecklist: "Failed", documents: "Missing", score: 38, risk: "High" },
  { name: "Abu Dhabi Corniche Cleaners", city: "Abu Dhabi", license: "Valid", agreement: "Signed", qualityChecklist: "Passed", documents: "Complete", score: 91, risk: "Low" },
];

export const complianceRiskTone: Record<"Low" | "Medium" | "High", Tone> = {
  Low: "success",
  Medium: "warning",
  High: "danger",
};

/* ------------------------------ Driver compliance --------------------------- */

export interface DriverCompliance {
  name: string;
  idDocs: "Valid" | "Expiring" | "Missing";
  training: "Complete" | "In Progress" | "Overdue";
  vehicleDocs: "Valid" | "Expiring" | "Missing";
  active: boolean;
  risk: "Low" | "Medium" | "High";
  /** Base city — geo signal for the global filters (privacy-safe, no address). */
  city: string;
}

export const driverCompliance: DriverCompliance[] = [
  { name: "Bilal Khan", idDocs: "Valid", training: "Complete", vehicleDocs: "Valid", active: true, risk: "Low", city: "Dubai" },
  { name: "Yousef Amir", idDocs: "Expiring", training: "Complete", vehicleDocs: "Valid", active: true, risk: "Medium", city: "Abu Dhabi" },
  { name: "Rashid Omar", idDocs: "Valid", training: "In Progress", vehicleDocs: "Expiring", active: true, risk: "Medium", city: "Doha" },
  { name: "Samir Haddad", idDocs: "Missing", training: "Overdue", vehicleDocs: "Valid", active: false, risk: "High", city: "Sharjah" },
  { name: "Tariq Nabil", idDocs: "Valid", training: "Complete", vehicleDocs: "Valid", active: true, risk: "Low", city: "Riyadh" },
];

/* ------------------------------ Documents & expiry -------------------------- */

export interface DocumentRow {
  document: string;
  ownerType: "Facility" | "Driver" | "Partner" | "Company";
  ownerName: string;
  expiry: string;
  status: "Valid" | "Expiring Soon" | "Expired";
  action: string;
  /** City of the owning facility/driver/partner (geo signal). */
  city?: string;
  /** Company-wide records bypass geo filters. */
  scope?: "global";
}

export const documents: DocumentRow[] = [
  { document: "Trade License", ownerType: "Facility", ownerName: "Doha West Bay Facility", expiry: "2026-08-05", status: "Expiring Soon", action: "Request renewal", city: "Doha" },
  { document: "Vehicle Insurance", ownerType: "Driver", ownerName: "Rashid Omar", expiry: "2026-08-02", status: "Expiring Soon", action: "Chase document", city: "Doha" },
  { document: "Trade License", ownerType: "Facility", ownerName: "Sharjah Industrial Cleaners", expiry: "2026-07-10", status: "Expired", action: "Suspend until renewed", city: "Sharjah" },
  { document: "Driver ID", ownerType: "Driver", ownerName: "Samir Haddad", expiry: "2026-07-15", status: "Expired", action: "Deactivate driver", city: "Sharjah" },
  { document: "Partner Agreement", ownerType: "Partner", ownerName: "Al Quoz Premium Cleaners", expiry: "2027-01-20", status: "Valid", action: "—", city: "Dubai" },
  { document: "VAT Registration", ownerType: "Company", ownerName: "LaundryKhalas FZ-LLC", expiry: "2026-12-31", status: "Valid", action: "—", scope: "global" },
];

export const docStatusTone: Record<DocumentRow["status"], Tone> = {
  Valid: "success",
  "Expiring Soon": "warning",
  Expired: "danger",
};

/* --------------------------------- Audit trail ------------------------------ */

export interface AuditRow {
  event: string;
  actor: string;
  module: string;
  /** ISO timestamp — recognized by the global date-range filter. */
  datetime: string;
  risk: "Low" | "Medium" | "High";
  notes: string;
  /** City the action relates to (geo signal); omitted for company-wide events. */
  city?: string;
  /** Company/partner-level actions bypass geo filters. */
  scope?: "global";
}

export const auditTrail: AuditRow[] = [
  { event: "Refund approved", actor: "Dana Aziz", module: "Finance", datetime: "2026-07-20T09:10:00Z", risk: "Medium", notes: "LK-24777 · duplicate charge reversal AED 176", city: "Doha" },
  { event: "Adjustment declined", actor: "Faris Al-Rashid", module: "Operations", datetime: "2026-07-20T08:40:00Z", risk: "Low", notes: "LK-24765 · outside policy", city: "Riyadh" },
  { event: "Facility flagged", actor: "System", module: "Compliance", datetime: "2026-07-20T08:05:00Z", risk: "High", notes: "Sharjah Industrial · license expired", city: "Sharjah" },
  { event: "Payout details updated", actor: "Dana Aziz", module: "Finance", datetime: "2026-07-19T17:20:00Z", risk: "Medium", notes: "Partner PA-1002 · bank reference masked", scope: "global" },
  { event: "Cost export generated", actor: "Dana Aziz", module: "Finance", datetime: "2026-07-19T16:00:00Z", risk: "Low", notes: "July cost breakdown · read-only", scope: "global" },
];

/* --------------------------------- Risk flags ------------------------------- */

export interface RiskFlag {
  id: string;
  flag: string;
  severity: "Low" | "Medium" | "High";
  detail: string;
  status: "Open" | "Investigating" | "Resolved";
  /** City the flag relates to (geo signal). */
  city?: string;
  /** System-wide flags (not tied to a city) bypass geo filters. */
  scope?: "global";
}

export const riskFlags: RiskFlag[] = [
  { id: "RK-01", flag: "Duplicate payment", severity: "High", detail: "Order LK-24777 charged twice — reversal approved", status: "Resolved", city: "Doha" },
  { id: "RK-02", flag: "Delayed refund", severity: "Medium", detail: "RF-9001 pending > 48h awaiting approval", status: "Open", city: "Dubai" },
  { id: "RK-03", flag: "High damage claims", severity: "Medium", detail: "Damage cost up 14% MoM — concentrated in Dubai", status: "Investigating", city: "Dubai" },
  { id: "RK-04", flag: "Missing partner documents", severity: "High", detail: "Sharjah Industrial · trade license expired", status: "Open", city: "Sharjah" },
  { id: "RK-05", flag: "Expiring license", severity: "Medium", detail: "Doha West Bay license expires in 16 days", status: "Open", city: "Doha" },
  { id: "RK-06", flag: "Unusual cost spike", severity: "Low", detail: "AI/LLM cost +26% — within projection", status: "Investigating", scope: "global" },
  { id: "RK-07", flag: "Payment failed repeatedly", severity: "High", detail: "Customer area Doha · 3 failed attempts", status: "Open", city: "Doha" },
];

export const riskSeverityTone: Record<"Low" | "Medium" | "High", Tone> = {
  Low: "info",
  Medium: "warning",
  High: "danger",
};

export const riskStatusTone: Record<RiskFlag["status"], Tone> = {
  Open: "warning",
  Investigating: "info",
  Resolved: "success",
};

/* ----------------------------------- Charts --------------------------------- */

export const complianceStatusChart: TimeSeriesPoint[] = [
  { label: "Passed", value: 41 },
  { label: "In Review", value: 9 },
  { label: "Docs Pending", value: 6 },
  { label: "Flagged", value: 3 },
];

export const paymentStatusChart: TimeSeriesPoint[] = paymentStatusRows.map((p) => ({ label: p.status, value: p.count }));

/* --------------------------------- Activity --------------------------------- */

export interface FinanceActivity {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
}

export const financeActivity: FinanceActivity[] = [
  { id: "fa1", title: "Refund awaiting approval", detail: "RF-9001 · AED 120 · damaged item", time: "2026-07-20T09:05:00Z", tone: "rose" },
  { id: "fa2", title: "Facility compliance flagged", detail: "Sharjah Industrial · license expired", time: "2026-07-20T08:05:00Z", tone: "danger" },
  { id: "fa3", title: "Duplicate payment resolved", detail: "LK-24777 · AED 176 reversed", time: "2026-07-20T07:30:00Z", tone: "success" },
  { id: "fa4", title: "Document expiring soon", detail: "Doha West Bay license · 16 days", time: "2026-07-19T18:00:00Z", tone: "warning" },
  { id: "fa5", title: "Weekly cost export ready", detail: "July cost breakdown · read-only", time: "2026-07-19T16:00:00Z", tone: "info" },
];

/* ---------------------- Detail-page getters + slug helpers ------------------ */
/**
 * Pure lookups for the click-through detail routes. Payment records and invoices
 * are read (never mutated) from operations-data; refunds/adjustments are this
 * section's own approval-gated records. Privacy: callers surface amount, method,
 * status, order id and area/city only — never card numbers, CVV or bank details.
 */
export function getPaymentRecord(orderId: string): PaymentRecord | undefined {
  return paymentRecords.find((p) => p.orderId === orderId);
}

export function getRefundAdjustment(id: string): RefundAdjustment | undefined {
  return refundsAdjustments.find((r) => r.id === id);
}

export function getInvoice(id: string): Invoice | undefined {
  return invoices.find((i) => i.id === id);
}

/** Whether a refund/adjustment can still be actioned (not yet finalised). */
export function refundIsActionable(approval: RefundAdjustment["approval"]): boolean {
  return approval === "Approval Required" || approval === "Pending Review";
}
