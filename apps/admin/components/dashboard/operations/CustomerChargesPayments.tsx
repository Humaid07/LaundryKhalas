"use client";

import {
  Wallet,
  Receipt,
  Clock,
  Undo2,
  PlusCircle,
  AlertTriangle,
  FileText,
  MapPin,
  Check,
  X,
  Send,
  StickyNote,
  Eye,
  BellRing,
  Info,
  ShieldCheck,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { Tabs, type TabDef } from "@/components/dashboard/ui/Tabs";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { formatCurrency } from "@/lib/dashboard/formatters";
import { priorityTone } from "@/lib/dashboard/status-maps";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterPayments, filterByArea, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import {
  paymentKpis,
  paymentRecords,
  pendingPayments,
  refundRequests,
  adjustments,
  paymentIssues,
  invoices,
  paymentActivity,
  paymentStatusTone,
  chargeStatusTone,
  approvalStatusTone,
  invoiceStatusTone,
  dueStatusTone,
  type PaymentRecord,
  type PendingPayment,
  type RefundRequest,
  type Adjustment,
  type PaymentIssue,
  type Invoice,
} from "@/lib/dashboard/operations-data";

const noMatch = <EmptyState icon={Wallet} title="No matches" description="No records match the active filters." />;
const money = (n: number) => formatCurrency(n);

/* ------------------------------ Payment overview ---------------------------- */

const overviewCols: Column<PaymentRecord>[] = [
  { key: "id", header: "Order", primary: true, cell: (p) => <span className="font-mono text-xs font-semibold text-ink">{p.orderId}</span> },
  { key: "customer", header: "Customer", cell: (p) => <span className="whitespace-nowrap text-ink">{p.customer}</span> },
  { key: "service", header: "Service", cell: (p) => <span className="whitespace-nowrap text-ink-muted">{p.service}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{money(p.amount)}</span> },
  { key: "method", header: "Method", cell: (p) => <StatusBadge tone="neutral" dot={false}>{p.method}</StatusBadge> },
  { key: "status", header: "Payment", cell: (p) => <StatusBadge tone={paymentStatusTone[p.status] ?? "neutral"}>{p.status}</StatusBadge> },
  { key: "charge", header: "Charge", cell: (p) => <StatusBadge tone={chargeStatusTone[p.chargeStatus] ?? "neutral"} dot={false}>{p.chargeStatus}</StatusBadge> },
  { key: "area", header: "City / Area", cell: (p) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
  { key: "channel", header: "Source", cell: (p) => <span className="text-xs text-ink-muted">{p.channel}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary"><Eye className="h-3.5 w-3.5" /> Details</Button> },
];

function OverviewTab({ rows }: { rows: PaymentRecord[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Payment overview" subtitle={`${rows.length} of ${paymentRecords.length} orders`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={overviewCols} rows={rows} rowKey={(p) => p.orderId} empty={noMatch} onRowLabel={(p) => <StatusBadge tone={paymentStatusTone[p.status] ?? "neutral"}>{p.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------ Pending payments ---------------------------- */

const pendingCols: Column<PendingPayment>[] = [
  { key: "id", header: "Order", primary: true, cell: (p) => <span className="font-mono text-xs font-semibold text-ink">{p.orderId}</span> },
  { key: "customer", header: "Customer", cell: (p) => <span className="whitespace-nowrap text-ink">{p.customer}</span> },
  { key: "amount", header: "Amount Due", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{money(p.amountDue)}</span> },
  { key: "method", header: "Method", cell: (p) => <StatusBadge tone="neutral" dot={false}>{p.method}</StatusBadge> },
  { key: "due", header: "Due Status", cell: (p) => <StatusBadge tone={dueStatusTone(p.dueStatus)}>{p.dueStatus}</StatusBadge> },
  { key: "delivery", header: "Delivery", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.deliveryStatus}</span> },
  { key: "followup", header: "Follow-up", cell: (p) => (p.followupNeeded ? <StatusBadge tone="warning" dot={false}>Needed</StatusBadge> : <span className="text-xs text-ink-faint">—</span>) },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary"><BellRing className="h-3.5 w-3.5" /> Follow-up</Button> },
];

function PendingTab({ rows }: { rows: PendingPayment[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Pending payments" subtitle={`${rows.length} awaiting collection`} className="p-4" action={<StatusBadge tone="warning">{rows.filter((r) => r.followupNeeded).length} need follow-up</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={pendingCols} rows={rows} rowKey={(p) => p.orderId} empty={noMatch} onRowLabel={(p) => <StatusBadge tone={dueStatusTone(p.dueStatus)}>{p.dueStatus}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------ Refund requests ----------------------------- */

function RefundsTab({ rows }: { rows: RefundRequest[] }) {
  return (
    <Panel>
      <PanelHeader
        title="Refund requests"
        subtitle="Every refund needs human approval before any money moves"
        action={<StatusBadge tone="danger">{rows.filter((r) => r.approvalStatus === "Approval Required").length} awaiting approval</StatusBadge>}
      />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <Undo2 className="mt-0.5 h-4 w-4 text-[rgb(var(--c-plum))]" />
              <div className="min-w-0">
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{r.id}</span> · {r.orderId} · {r.customer}</p>
                <p className="text-xs text-ink-muted">{r.reason} · {money(r.amount)}</p>
                <p className="flex items-center gap-1 text-xxs text-ink-faint"><MapPin className="h-3 w-3" /> {r.area} · order {r.orderStatus} · {r.paymentStatus}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 pl-7 lg:pl-0">
              <StatusBadge tone={priorityTone[r.urgency]} dot={false}>{r.urgency}</StatusBadge>
              <StatusBadge tone={approvalStatusTone[r.approvalStatus]}>{r.approvalStatus}</StatusBadge>
              {r.approvalStatus === "Approval Required" || r.approvalStatus === "Pending Review" ? (
                <Button size="sm" variant="primary">Raise refund review</Button>
              ) : (
                <Button size="sm" variant="ghost">View</Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 flex items-center gap-1.5 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Refunds route through approval to Finance before processing.</p>
    </Panel>
  );
}

/* --------------------------- Adjustments / charges -------------------------- */

function AdjustmentsTab({ rows }: { rows: Adjustment[] }) {
  return (
    <Panel>
      <PanelHeader title="Adjustments / extra charges" subtitle="Extra charges above the quote need approval" action={<StatusBadge tone="warning">{rows.filter((a) => a.approvalStatus === "Approval Required").length} pending</StatusBadge>} />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((a) => (
          <li key={a.orderId} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <PlusCircle className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div className="min-w-0">
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{a.orderId}</span> · {a.customer}</p>
                <p className="text-xs text-ink-muted">{a.reason}</p>
                <p className="text-xxs text-ink-faint">{money(a.originalAmount)} + <span className="text-warning">{money(a.extraCharge)}</span> = <span className="font-semibold text-ink">{money(a.finalAmount)}</span></p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 lg:pl-0">
              <StatusBadge tone={approvalStatusTone[a.approvalStatus]}>{a.approvalStatus}</StatusBadge>
              {a.approvalStatus === "Approval Required" ? (
                <>
                  <Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button>
                  <Button size="sm" variant="danger"><X className="h-3.5 w-3.5" /> Reject</Button>
                </>
              ) : (
                <Button size="sm" variant="ghost">View</Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 flex items-center gap-1.5 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Approve/Reject route through approval before any customer is charged.</p>
    </Panel>
  );
}

/* ------------------------------- Payment issues ----------------------------- */

const issueCols: Column<PaymentIssue>[] = [
  { key: "id", header: "Issue", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-ink">{i.id}</span> },
  { key: "order", header: "Order", cell: (i) => <span className="font-mono text-xs text-ink-muted">{i.orderId}</span> },
  { key: "customer", header: "Customer", cell: (i) => <span className="whitespace-nowrap text-ink-muted">{i.customer}</span> },
  { key: "type", header: "Issue Type", cell: (i) => <span className="text-ink">{i.issueType}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (i) => <span className="font-mono text-sm text-ink tnum">{money(i.amount)}</span> },
  { key: "method", header: "Method", cell: (i) => <StatusBadge tone="neutral" dot={false}>{i.method}</StatusBadge> },
  { key: "priority", header: "Priority", cell: (i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge> },
  { key: "team", header: "Assigned Team", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{i.assignedTeam}</span> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"}>{i.status}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Manage</Button> },
];

function IssuesTab({ rows }: { rows: PaymentIssue[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Payment issues" subtitle="Failed charges, uncollected cash, duplicates & disputes" className="p-4" action={<StatusBadge tone="warning">{rows.filter((i) => i.status !== "Resolved").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={issueCols} rows={rows} rowKey={(i) => i.id} empty={noMatch} onRowLabel={(i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Invoices / B2B ----------------------------- */

const invoiceCols: Column<Invoice>[] = [
  { key: "id", header: "Invoice", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-ink">{i.id}</span> },
  { key: "customer", header: "Business Customer", cell: (i) => <span className="whitespace-nowrap text-ink">{i.businessCustomer}</span> },
  { key: "service", header: "Service", cell: (i) => <span className="whitespace-nowrap text-ink-muted">{i.service}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (i) => <span className="font-mono text-sm text-ink tnum">{money(i.amount)}</span> },
  { key: "period", header: "Billing Period", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{i.billingPeriod}</span> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={invoiceStatusTone[i.status] ?? "neutral"}>{i.status}</StatusBadge> },
  { key: "due", header: "Due Date", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{i.dueDate}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary"><Send className="h-3.5 w-3.5" /> Send</Button> },
];

function InvoicesTab({ rows }: { rows: Invoice[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Invoices / B2B" subtitle="Business customer billing" className="p-4" action={<StatusBadge tone="danger">{rows.filter((i) => i.status === "Overdue").length} overdue</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={invoiceCols} rows={rows} rowKey={(i) => i.id} empty={noMatch} onRowLabel={(i) => <StatusBadge tone={invoiceStatusTone[i.status] ?? "neutral"}>{i.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* --------------------------------- Section ---------------------------------- */

export function CustomerChargesPayments() {
  const { filters } = useFilters();
  const fOverview = filterPayments(paymentRecords, filters);
  const fPending = filterByArea(pendingPayments, filters);
  const fRefunds = filterByArea(refundRequests, filters);
  const fAdjustments = filterByArea(adjustments, filters);
  const fIssues = filterByArea(paymentIssues, filters);
  // Invoices are B2B; they now carry billing city + channel so they filter by geo.
  const fInvoices = applyGlobalFilters(invoices, filters);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: TabDef[] = [
    { id: "overview", label: "Payment Overview", icon: <Receipt className="h-4 w-4" />, content: <OverviewTab rows={fOverview} /> },
    { id: "pending", label: "Pending Payments", icon: <Clock className="h-4 w-4" />, badge: fPending.length, content: <PendingTab rows={fPending} /> },
    { id: "refunds", label: "Refund Requests", icon: <Undo2 className="h-4 w-4" />, badge: fRefunds.filter((r) => r.approvalStatus === "Approval Required").length, content: <RefundsTab rows={fRefunds} /> },
    { id: "adjustments", label: "Adjustments / Extra Charges", icon: <PlusCircle className="h-4 w-4" />, badge: fAdjustments.filter((a) => a.approvalStatus === "Approval Required").length, content: <AdjustmentsTab rows={fAdjustments} /> },
    { id: "issues", label: "Payment Issues", icon: <AlertTriangle className="h-4 w-4" />, badge: fIssues.filter((i) => i.status !== "Resolved").length, content: <IssuesTab rows={fIssues} /> },
    { id: "invoices", label: "Invoices / B2B", icon: <FileText className="h-4 w-4" />, content: <InvoicesTab rows={fInvoices} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Payments snapshot</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={paymentKpis} cols="4" />
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <Tabs tabs={tabs} />
        </div>
        <aside className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Operational payment view</p>
              <p className="text-xxs text-ink-muted">Customer-level payment operations only. Financial summaries — revenue, cost, margin — remain in the Finance section.</p>
            </div>
          </div>
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Approval-gated · privacy-safe</p>
              <p className="text-xxs text-ink-muted">Refunds & adjustments require human approval. No card numbers, CVV or bank details are stored.</p>
            </div>
          </div>
          <Panel>
            <PanelHeader title="Payment activity" subtitle="Latest payment-side events" />
            <ActivityTimeline events={paymentActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Payment actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "View Payment Details", icon: Eye },
                { label: "Mark as Paid", icon: Check },
                { label: "Request Follow-up", icon: BellRing },
                { label: "Raise Refund Review", icon: Undo2 },
                { label: "Approve Adjustment", icon: Check },
                { label: "Reject Adjustment", icon: X },
                { label: "Send to Finance", icon: Send },
                { label: "Add Internal Note", icon: StickyNote },
              ].map((a) => (
                <button key={a.label} type="button" className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-2.5 py-2 text-left text-xs font-medium text-ink transition-colors hover:border-rose/40">
                  <a.icon className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                  <span className="truncate">{a.label}</span>
                </button>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
