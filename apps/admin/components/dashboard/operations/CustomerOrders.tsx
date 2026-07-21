"use client";

import {
  ClipboardList,
  ListChecks,
  CheckCircle2,
  Ban,
  AlertTriangle,
  Pencil,
  MapPin,
  Eye,
  Navigation,
  Star,
  Check,
  X,
  ShieldCheck,
  Truck,
  Building2,
  StickyNote,
  Info,
} from "lucide-react";
import { useMemo } from "react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { Tabs, type TabDef } from "@/components/dashboard/ui/Tabs";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { LocalFilterBar, useLocalFilters, matchesLocal, type LocalFilterDef } from "@/components/dashboard/ui/LocalFilters";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterOrders, filterByOrderRef, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { orderStatusTone, paymentTone, priorityTone, riskTone } from "@/lib/dashboard/status-maps";
import { orders } from "@/lib/dashboard/mock-data";
import {
  customerOrdersKpis,
  orderChanges,
  orderIssues,
  orderIssueStatusTone,
  orderCenterActivity,
  nextStepByStatus,
  orderSla,
  orderRatings,
  ACTIVE_EXCLUDED,
  type OrderChange,
  type OrderIssue,
} from "@/lib/dashboard/operations-data";
import type { Order } from "@/lib/dashboard/types";

const noMatch = <EmptyState icon={ClipboardList} title="No matches" description="No orders match the active filters." />;
const money = (n: number) => formatCurrency(n);

const ORDER_STATUSES = [
  "New", "Pickup Scheduled", "Driver Assigned", "Picked Up", "In Cleaning",
  "Ready for Delivery", "Out for Delivery", "Delivered", "Cancelled", "Concern Raised",
];
const PAYMENT_STATUSES = ["Paid", "Pending", "Refunded", "Failed"];

/* -------------------------------- All orders -------------------------------- */

const allCols: Column<Order>[] = [
  { key: "id", header: "Order ID", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "customer", header: "Customer", cell: (o) => <span className="whitespace-nowrap text-ink">{o.customer}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service}</span> },
  { key: "channel", header: "Source", cell: (o) => <StatusBadge tone="neutral" dot={false}>{o.channel}</StatusBadge> },
  { key: "city", header: "City / Area", cell: (o) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{o.city}</span> },
  { key: "status", header: "Status", cell: (o) => <StatusBadge tone={orderStatusTone[o.status]}>{o.status}</StatusBadge> },
  { key: "pickup", header: "Pickup Slot", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{o.pickupSlot}</span> },
  { key: "facility", header: "Facility", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{o.facility}</span> },
  { key: "driver", header: "Driver", cell: (o) => (o.driver ? <span className="whitespace-nowrap text-ink-muted">{o.driver}</span> : <StatusBadge tone="warning" dot={false}>Unassigned</StatusBadge>) },
  { key: "amount", header: "Amount", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{money(o.amount)}</span> },
  { key: "payment", header: "Payment", cell: (o) => <StatusBadge tone={paymentTone[o.payment]} dot={false}>{o.payment}</StatusBadge> },
  {
    key: "actions", header: "", align: "right",
    cell: () => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" aria-label="View order"><Eye className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="ghost" aria-label="Track order"><Navigation className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="secondary">Manage</Button>
      </div>
    ),
  },
];

function AllOrdersTab({ rows, total }: { rows: Order[]; total: number }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="All customer orders" subtitle={`${rows.length} of ${total} orders · WhatsApp, website, app, B2B & manual`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={allCols} rows={rows} rowKey={(o) => o.id} empty={noMatch} onRowLabel={(o) => <StatusBadge tone={orderStatusTone[o.status]}>{o.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Active orders ------------------------------ */

const activeCols: Column<Order>[] = [
  { key: "id", header: "Order ID", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "customer", header: "Customer", cell: (o) => <span className="whitespace-nowrap text-ink">{o.customer}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service}</span> },
  { key: "status", header: "Current Status", cell: (o) => <StatusBadge tone={orderStatusTone[o.status]}>{o.status}</StatusBadge> },
  { key: "next", header: "Next Step", cell: (o) => <span className="text-xs text-ink-faint">{nextStepByStatus[o.status] ?? "—"}</span> },
  { key: "facility", header: "Facility", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{o.facility}</span> },
  { key: "driver", header: "Driver", cell: (o) => (o.driver ? <span className="whitespace-nowrap text-ink-muted">{o.driver}</span> : <StatusBadge tone="warning" dot={false}>Unassigned</StatusBadge>) },
  { key: "sla", header: "SLA", cell: (o) => { const s = orderSla(o.status); return <StatusBadge tone={s.tone} dot={false}>{s.label}</StatusBadge>; } },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Manage</Button> },
];

function ActiveOrdersTab({ rows }: { rows: Order[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Active orders" subtitle={`${rows.length} in progress · not yet delivered or cancelled`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={activeCols} rows={rows} rowKey={(o) => o.id} empty={noMatch} onRowLabel={(o) => <StatusBadge tone={orderStatusTone[o.status]}>{o.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ----------------------------- Completed orders ----------------------------- */

const completedCols: Column<Order>[] = [
  { key: "id", header: "Order ID", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "customer", header: "Customer", cell: (o) => <span className="whitespace-nowrap text-ink">{o.customer}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service}</span> },
  { key: "completed", header: "Completed At", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{o.pickupSlot}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{money(o.amount)}</span> },
  { key: "payment", header: "Payment", cell: (o) => <StatusBadge tone={paymentTone[o.payment]} dot={false}>{o.payment}</StatusBadge> },
  { key: "rating", header: "Rating", cell: (o) => (orderRatings[o.id] ? <span className="flex items-center gap-1 whitespace-nowrap font-mono text-xs text-ink tnum"><Star className="h-3 w-3 text-warning" />{orderRatings[o.id].toFixed(1)}</span> : <span className="text-xs text-ink-faint">—</span>) },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="ghost">View</Button> },
];

function CompletedOrdersTab({ rows }: { rows: Order[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Completed orders" subtitle={`${rows.length} delivered`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={completedCols} rows={rows} rowKey={(o) => o.id} empty={<EmptyState icon={CheckCircle2} title="No completed orders" description="Delivered orders will appear here." />} />
      </div>
    </Panel>
  );
}

/* ----------------------------- Cancelled orders ----------------------------- */

const cancelledCols: Column<Order>[] = [
  { key: "id", header: "Order ID", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "customer", header: "Customer", cell: (o) => <span className="whitespace-nowrap text-ink">{o.customer}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service}</span> },
  { key: "channel", header: "Source", cell: (o) => <StatusBadge tone="neutral" dot={false}>{o.channel}</StatusBadge> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{money(o.amount)}</span> },
  { key: "payment", header: "Payment", cell: (o) => <StatusBadge tone={paymentTone[o.payment]} dot={false}>{o.payment}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="ghost">View</Button> },
];

function CancelledOrdersTab({ rows }: { rows: Order[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Cancelled orders" subtitle={`${rows.length} cancelled`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={cancelledCols} rows={rows} rowKey={(o) => o.id} empty={<EmptyState icon={Ban} title="No cancelled orders" description="Cancelled orders will appear here." />} />
      </div>
    </Panel>
  );
}

/* --------------------------- Orders with issues ----------------------------- */

const issueCols: Column<OrderIssue>[] = [
  { key: "order", header: "Order ID", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-ink">{i.orderId}</span> },
  { key: "customer", header: "Customer", cell: (i) => <span className="whitespace-nowrap text-ink">{i.customer}</span> },
  { key: "type", header: "Issue Type", cell: (i) => <span className="text-ink-muted">{i.issueType}</span> },
  { key: "priority", header: "Priority", cell: (i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge> },
  { key: "team", header: "Assigned Team", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{i.assignedTeam}</span> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={orderIssueStatusTone[i.status]}>{i.status}</StatusBadge> },
  { key: "updated", header: "Last Update", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(i.lastUpdate)}</span> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Manage</Button> },
];

function IssuesTab({ rows }: { rows: OrderIssue[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Orders with issues" subtitle="Damage, delays, lost items, quality & billing" className="p-4" action={<StatusBadge tone="warning">{rows.filter((i) => i.status !== "Resolved").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={issueCols} rows={rows} rowKey={(i) => i.id} empty={<EmptyState icon={AlertTriangle} title="No issues" description="Orders with issues appear here." />} onRowLabel={(i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Order changes ------------------------------ */

function ChangesTab({ rows }: { rows: OrderChange[] }) {
  return (
    <Panel>
      <PanelHeader title="Order change requests" subtitle="Every change is logged and needs approval" action={<StatusBadge tone="warning">{rows.filter((c) => c.status === "Awaiting Approval").length} pending</StatusBadge>} />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((c) => (
          <li key={c.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Pencil className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div>
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{c.orderId}</span> · {c.customer}</p>
                <p className="text-xs text-ink-muted">{c.change}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 sm:pl-0">
              <StatusBadge tone={riskTone[c.risk]} dot={false}>{c.risk} risk</StatusBadge>
              {c.status === "Applied" ? (
                <StatusBadge tone="success">Applied</StatusBadge>
              ) : (
                <>
                  <Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button>
                  <Button size="sm" variant="danger"><X className="h-3.5 w-3.5" /> Reject</Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* --------------------------------- Section ---------------------------------- */

export function CustomerOrders() {
  const { filters } = useFilters();
  const orderIndex = useMemo(() => new Map(orders.map((o) => [o.id, o])), []);

  // Local (order-specific) filters layered on top of the global geo filters.
  const localDefs: LocalFilterDef[] = [
    { key: "status", label: "Order status", options: ORDER_STATUSES },
    { key: "payment", label: "Payment status", options: PAYMENT_STATUSES },
  ];
  const lf = useLocalFilters(localDefs);

  const base = filterOrders(orders, filters);
  const withLocal = base.filter((o) =>
    matchesLocal(o, lf.values, (row, key) => (key === "payment" ? row.payment : row.status)),
  );

  const activeRows = withLocal.filter((o) => !ACTIVE_EXCLUDED.has(o.status));
  const completedRows = base.filter((o) => o.status === "Delivered");
  const cancelledRows = base.filter((o) => o.status === "Cancelled");
  const fChanges = filterByOrderRef(orderChanges, filters, orderIndex);
  const fIssues = applyGlobalFilters(orderIssues, filters);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: TabDef[] = [
    { id: "all", label: "All Orders", icon: <ClipboardList className="h-4 w-4" />, content: <AllOrdersTab rows={withLocal} total={orders.length} /> },
    { id: "active", label: "Active Orders", icon: <ListChecks className="h-4 w-4" />, badge: activeRows.length, content: <ActiveOrdersTab rows={activeRows} /> },
    { id: "completed", label: "Completed Orders", icon: <CheckCircle2 className="h-4 w-4" />, content: <CompletedOrdersTab rows={completedRows} /> },
    { id: "cancelled", label: "Cancelled Orders", icon: <Ban className="h-4 w-4" />, content: <CancelledOrdersTab rows={cancelledRows} /> },
    { id: "issues", label: "Orders With Issues", icon: <AlertTriangle className="h-4 w-4" />, badge: fIssues.filter((i) => i.status !== "Resolved").length, content: <IssuesTab rows={fIssues} /> },
    { id: "changes", label: "Order Changes", icon: <Pencil className="h-4 w-4" />, badge: fChanges.filter((c) => c.status !== "Applied").length, content: <ChangesTab rows={fChanges} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Order center snapshot</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={customerOrdersKpis} cols="auto" />
      <div className="space-y-2.5 rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
        <div className="border-t border-border pt-2.5">
          <LocalFilterBar defs={localDefs} values={lf.values} onChange={lf.set} onClear={lf.clear} />
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <Tabs tabs={tabs} />
        </div>
        <aside className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Order center</p>
              <p className="text-xxs text-ink-muted">All orders across channels in one place. Customer support conversations live under Customer Facing; refunds & payment analytics under Finance &amp; Compliance.</p>
            </div>
          </div>
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Approval-gated</p>
              <p className="text-xxs text-ink-muted">Reads from <span className="font-mono">/api/orders/*</span>. Cancellations & changes require approval before they take effect.</p>
            </div>
          </div>
          <Panel>
            <PanelHeader title="Order activity" subtitle="Latest order-center events" />
            <ActivityTimeline events={orderCenterActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Order actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "View Order", icon: Eye },
                { label: "Track Order", icon: Navigation },
                { label: "Assign Driver", icon: Truck },
                { label: "Assign Facility", icon: Building2 },
                { label: "Change Details", icon: Pencil },
                { label: "Cancel Order", icon: Ban },
                { label: "Mark Completed", icon: CheckCircle2 },
                { label: "Raise Ticket", icon: AlertTriangle },
                { label: "Add Note", icon: StickyNote },
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
