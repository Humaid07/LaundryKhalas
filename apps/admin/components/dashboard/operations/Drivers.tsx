"use client";

import {
  Truck,
  UserRound,
  PackageOpen,
  PackageCheck,
  AlertTriangle,
  MapPin,
  Clock,
  ArrowRight,
  Play,
  Check,
  Phone,
  Route,
  RefreshCw,
  Gauge,
  Star,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { Tabs, type TabDef } from "@/components/dashboard/ui/Tabs";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { FilteredEmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterDrivers, filterByArea, applyGlobalFilters, filterContextLabel, activeFilterCount } from "@/lib/dashboard/filters";
import { priorityTone } from "@/lib/dashboard/status-maps";
import {
  driverKpis,
  drivers,
  pickupQueue,
  deliveryQueue,
  driverPerformance,
  driverIssues,
  driverActivity,
  driverStatusTone,
  pickupStatusTone,
  deliveryStatusTone,
  facilityPriorityTone,
  paymentStatusTone,
  type Driver,
  type PickupJob,
  type DeliveryJob,
  type DriverPerformance,
  type DriverIssue,
} from "@/lib/dashboard/operations-data";
import { cn } from "@/lib/utils";

/** Filter-aware empty state: names the active scope and offers a one-click reset. */
function FilteredNoMatch({ entity = "records" }: { entity?: string }) {
  const { filters, clearAll } = useFilters();
  return <FilteredEmptyState entity={entity} context={filterContextLabel(filters)} onClear={clearAll} />;
}
const noMatch = <FilteredNoMatch />;

/* ------------------------------ Driver overview ----------------------------- */

const driverCols: Column<Driver>[] = [
  { key: "name", header: "Driver", primary: true, cell: (d) => <span className="font-medium text-ink">{d.name}</span> },
  { key: "status", header: "Status", cell: (d) => <StatusBadge tone={driverStatusTone[d.status]}>{d.status}</StatusBadge> },
  { key: "zone", header: "Zone", cell: (d) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{d.zone}</span> },
  { key: "assigned", header: "Assigned", align: "right", cell: (d) => <span className="font-mono text-sm text-ink tnum">{d.assignedOrders}</span> },
  { key: "completed", header: "Done today", align: "right", cell: (d) => <span className="font-mono text-sm text-ink-muted tnum">{d.completedToday}</span> },
  { key: "delayed", header: "Delayed", align: "right", cell: (d) => <span className={cn("font-mono text-sm tnum", d.delayedJobs > 0 ? "text-danger" : "text-ink-faint")}>{d.delayedJobs}</span> },
  { key: "rating", header: "Rating / PPI", cell: (d) => <span className="flex items-center gap-1 whitespace-nowrap font-mono text-xs text-ink tnum"><Star className="h-3 w-3 text-warning" />{d.rating.toFixed(1)} · {d.ppiScore}</span> },
  { key: "active", header: "Last active", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(d.lastActive)}</span> },
  {
    key: "actions",
    header: "",
    align: "right",
    cell: () => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" aria-label="View route"><Route className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="ghost" aria-label="Contact driver"><Phone className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="secondary">Assign</Button>
      </div>
    ),
  },
];

function DriverOverviewTab({ rows }: { rows: Driver[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Driver overview" subtitle={`${rows.length} of ${drivers.length} drivers · pickup & delivery fleet`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={driverCols} rows={rows} rowKey={(d) => d.name} empty={noMatch} onRowLabel={(d) => <StatusBadge tone={driverStatusTone[d.status]}>{d.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Pickup queue ------------------------------- */

const pickupCols: Column<PickupJob>[] = [
  { key: "id", header: "Order", primary: true, cell: (p) => <span className="font-mono text-xs font-semibold text-ink">{p.orderId}</span> },
  // Privacy: area/city only — no customer name, phone or full address.
  { key: "area", header: "Customer Area", cell: (p) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
  { key: "service", header: "Service", cell: (p) => <span className="whitespace-nowrap text-ink-muted">{p.service}</span> },
  { key: "slot", header: "Pickup Slot", cell: (p) => <span className="whitespace-nowrap text-xs text-ink-muted">{p.pickupSlot}</span> },
  { key: "driver", header: "Driver", cell: (p) => (p.driver ? <span className="whitespace-nowrap text-ink">{p.driver}</span> : <StatusBadge tone="warning" dot={false}>Unassigned</StatusBadge>) },
  { key: "status", header: "Status", cell: (p) => <StatusBadge tone={pickupStatusTone[p.status]}>{p.status}</StatusBadge> },
  { key: "priority", header: "Priority", cell: (p) => <StatusBadge tone={facilityPriorityTone[p.priority]} dot={false}>{p.priority}</StatusBadge> },
  { key: "notes", header: "Notes", cell: (p) => <span className="text-xs text-ink-faint">{p.notes || "—"}</span> },
  {
    key: "actions",
    header: "",
    align: "right",
    cell: (p) => (
      <div className="flex justify-end gap-1">
        {p.driver ? (
          <Button size="sm" variant="secondary"><Play className="h-3.5 w-3.5" /> Start</Button>
        ) : (
          <Button size="sm" variant="primary">Assign <ArrowRight className="h-3.5 w-3.5" /></Button>
        )}
      </div>
    ),
  },
];

function PickupQueueTab({ rows }: { rows: PickupJob[] }) {
  const unassigned = rows.filter((p) => !p.driver).length;
  return (
    <Panel padded={false}>
      <PanelHeader title="Pickup queue" subtitle={`${rows.length} pickups · ${unassigned} awaiting a driver · area/city only`} className="p-4" action={unassigned > 0 ? <StatusBadge tone="warning">{unassigned} unassigned</StatusBadge> : undefined} />
      <div className="px-4 pb-4">
        <DataTable columns={pickupCols} rows={rows} rowKey={(p) => p.orderId} empty={noMatch} onRowLabel={(p) => <StatusBadge tone={pickupStatusTone[p.status]}>{p.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ------------------------------ Delivery queue ------------------------------ */

const deliveryCols: Column<DeliveryJob>[] = [
  { key: "id", header: "Order", primary: true, cell: (d) => <span className="font-mono text-xs font-semibold text-ink">{d.orderId}</span> },
  { key: "area", header: "Customer Area", cell: (d) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{d.area}</span> },
  { key: "service", header: "Service", cell: (d) => <span className="whitespace-nowrap text-ink-muted">{d.service}</span> },
  { key: "slot", header: "Delivery Slot", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{d.deliverySlot}</span> },
  { key: "driver", header: "Driver", cell: (d) => (d.driver ? <span className="whitespace-nowrap text-ink">{d.driver}</span> : <StatusBadge tone="warning" dot={false}>Unassigned</StatusBadge>) },
  { key: "facility", header: "Facility", cell: (d) => <span className="whitespace-nowrap text-ink-muted">{d.facility}</span> },
  { key: "status", header: "Status", cell: (d) => <StatusBadge tone={deliveryStatusTone[d.status]}>{d.status}</StatusBadge> },
  { key: "payment", header: "Payment", cell: (d) => <StatusBadge tone={paymentStatusTone[d.paymentStatus] ?? "neutral"} dot={false}>{d.paymentStatus}</StatusBadge> },
  {
    key: "actions",
    header: "",
    align: "right",
    cell: (d) => (
      <div className="flex justify-end gap-1">
        {d.status === "Delivered" ? (
          <Button size="sm" variant="ghost">View</Button>
        ) : d.driver ? (
          <Button size="sm" variant="secondary"><Check className="h-3.5 w-3.5" /> Delivered</Button>
        ) : (
          <Button size="sm" variant="primary">Assign <ArrowRight className="h-3.5 w-3.5" /></Button>
        )}
      </div>
    ),
  },
];

function DeliveryQueueTab({ rows }: { rows: DeliveryJob[] }) {
  const unassigned = rows.filter((d) => !d.driver).length;
  return (
    <Panel padded={false}>
      <PanelHeader title="Delivery queue" subtitle={`${rows.length} deliveries · ${unassigned} awaiting a driver · area/city only`} className="p-4" action={unassigned > 0 ? <StatusBadge tone="warning">{unassigned} unassigned</StatusBadge> : undefined} />
      <div className="px-4 pb-4">
        <DataTable columns={deliveryCols} rows={rows} rowKey={(d) => d.orderId} empty={noMatch} onRowLabel={(d) => <StatusBadge tone={deliveryStatusTone[d.status]}>{d.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ---------------------------- Driver performance ---------------------------- */

const performanceCols: Column<DriverPerformance>[] = [
  { key: "driver", header: "Driver", primary: true, cell: (p) => <span className="font-medium text-ink">{p.driver}</span> },
  { key: "completed", header: "Completed", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.completedToday}</span> },
  {
    key: "ontime",
    header: "On-time",
    cell: (p) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/8">
          <div className={cn("h-full rounded-full", p.onTimePct >= 95 ? "bg-success" : p.onTimePct >= 88 ? "bg-warning" : "bg-danger")} style={{ width: `${p.onTimePct}%` }} />
        </div>
        <span className="font-mono text-xs text-ink-muted tnum">{p.onTimePct}%</span>
      </div>
    ),
  },
  { key: "pickup", header: "Avg pickup", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.avgPickup}</span> },
  { key: "delivery", header: "Avg delivery", align: "right", cell: (p) => <span className="font-mono text-xs text-ink-muted tnum">{p.avgDelivery}</span> },
  { key: "rating", header: "Rating", cell: (p) => <span className="flex items-center gap-1 whitespace-nowrap font-mono text-xs text-ink tnum"><Star className="h-3 w-3 text-warning" />{p.rating.toFixed(1)}</span> },
  { key: "ppi", header: "PPI", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.ppiScore}</span> },
];

function PerformanceTab({ rows }: { rows: DriverPerformance[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Driver performance" subtitle="On-time rate, turnaround and PPI score" className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={performanceCols} rows={rows} rowKey={(p) => p.driver} empty={noMatch} />
      </div>
    </Panel>
  );
}

/* ------------------------------- Driver issues ------------------------------ */

const issueCols: Column<DriverIssue>[] = [
  { key: "id", header: "Issue", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-ink">{i.id}</span> },
  { key: "driver", header: "Driver", cell: (i) => <span className="whitespace-nowrap text-ink-muted">{i.driver}</span> },
  { key: "order", header: "Order", cell: (i) => <span className="font-mono text-xs text-ink-muted">{i.orderId}</span> },
  { key: "type", header: "Issue Type", cell: (i) => <span className="text-ink">{i.issueType}</span> },
  { key: "priority", header: "Priority", cell: (i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"}>{i.status}</StatusBadge> },
  { key: "reported", header: "Reported", cell: (i) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(i.reportedAt)}</span> },
  { key: "action", header: "Action Needed", cell: (i) => <span className="text-xs text-ink-faint">{i.actionNeeded}</span> },
  { key: "manage", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Manage</Button> },
];

function IssuesTab({ rows }: { rows: DriverIssue[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Driver issues" subtitle="Pickup/delivery problems needing ops action" className="p-4" action={<StatusBadge tone="warning">{rows.filter((i) => i.status !== "Resolved").length} open</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={issueCols} rows={rows} rowKey={(i) => i.id} empty={noMatch} onRowLabel={(i) => <StatusBadge tone={priorityTone[i.priority]} dot={false}>{i.priority}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* --------------------------------- Section ---------------------------------- */

export function Drivers() {
  const { filters } = useFilters();
  const fDrivers = filterDrivers(drivers, filters);
  const fPickups = filterByArea(pickupQueue, filters);
  const fDeliveries = filterByArea(deliveryQueue, filters);
  const fPerformance = applyGlobalFilters(driverPerformance, filters);
  const fIssues = applyGlobalFilters(driverIssues, filters);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: TabDef[] = [
    { id: "overview", label: "Driver Overview", icon: <UserRound className="h-4 w-4" />, content: <DriverOverviewTab rows={fDrivers} /> },
    { id: "pickup", label: "Pickup Queue", icon: <PackageOpen className="h-4 w-4" />, badge: fPickups.filter((p) => !p.driver).length, content: <PickupQueueTab rows={fPickups} /> },
    { id: "delivery", label: "Delivery Queue", icon: <PackageCheck className="h-4 w-4" />, badge: fDeliveries.filter((d) => !d.driver).length, content: <DeliveryQueueTab rows={fDeliveries} /> },
    { id: "performance", label: "Driver Performance", icon: <Gauge className="h-4 w-4" />, content: <PerformanceTab rows={fPerformance} /> },
    { id: "issues", label: "Driver Issues", icon: <AlertTriangle className="h-4 w-4" />, badge: fIssues.filter((i) => i.status !== "Resolved").length, content: <IssuesTab rows={fIssues} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Fleet snapshot</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={driverKpis} cols="4" />
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <Tabs tabs={tabs} />
        </div>
        <aside className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Privacy firewall on</p>
              <p className="text-xxs text-ink-muted">Driver views show area/city (e.g. Dubai Marina) — full address is an authorized detail view only. No customer phone, email or name in tables.</p>
            </div>
          </div>
          <Panel>
            <PanelHeader title="Driver activity" subtitle="Latest fleet events" />
            <ActivityTimeline events={driverActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Driver actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Assign Driver", icon: UserRound },
                { label: "Reassign Driver", icon: RefreshCw },
                { label: "Mark Pickup Started", icon: Play },
                { label: "Mark Picked Up", icon: PackageOpen },
                { label: "Mark Delivery Started", icon: Truck },
                { label: "Mark Delivered", icon: PackageCheck },
                { label: "Report Issue", icon: AlertTriangle },
                { label: "Contact Driver", icon: Phone },
                { label: "View Route", icon: Route },
                { label: "Track ETA", icon: Clock },
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
