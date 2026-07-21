"use client";

import {
  Boxes,
  Building2,
  RefreshCw,
  AlertTriangle,
  BadgeCheck,
  Truck,
  MapPin,
  Clock,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { useMemo } from "react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { Tabs, type TabDef } from "@/components/dashboard/ui/Tabs";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, FilteredEmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterFacilityOrders, filterFacilities, filterByArea, applyGlobalFilters, filterContextLabel, activeFilterCount } from "@/lib/dashboard/filters";
import {
  facilityFacingKpis,
  facilities,
  facilityOrders,
  facilityIssues,
  qualityChecks,
  deliveryHandoff,
  facilityActivity,
  facilityStatusTone,
  facilityOrderStatusTone,
  qualityTone,
  facilityPriorityTone,
  severityTone,
  handoffTone,
  type Facility,
  type FacilityOrder,
  type QualityCheck,
  type HandoffOrder,
} from "@/lib/dashboard/operations-data";
import { cn } from "@/lib/utils";

/* ------------------------------ Facility orders ----------------------------- */

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

const orderCols: Column<FacilityOrder>[] = [
  { key: "id", header: "Order", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "facility", header: "Facility", cell: (o) => <span className="whitespace-nowrap text-ink">{o.facility}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="whitespace-nowrap text-ink-muted">{o.service}</span> },
  { key: "items", header: "Items", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{o.items}</span> },
  // Privacy: area/city only — no customer name, phone, email or full address.
  { key: "area", header: "Area", cell: (o) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{o.area}</span> },
  { key: "status", header: "Status", cell: (o) => <StatusBadge tone={facilityOrderStatusTone[o.status]}>{o.status}</StatusBadge> },
  { key: "priority", header: "Priority", cell: (o) => <StatusBadge tone={facilityPriorityTone[o.priority]} dot={false}>{o.priority}</StatusBadge> },
  { key: "eta", header: "Expected", cell: (o) => <span className="whitespace-nowrap text-xs text-ink-muted">{fmtTime(o.expectedCompletion)}</span> },
  { key: "quality", header: "QC", cell: (o) => <StatusBadge tone={qualityTone[o.quality]} dot={false}>{o.quality}</StatusBadge> },
  {
    key: "actions",
    header: "",
    align: "right",
    cell: () => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" aria-label="Update status"><RefreshCw className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="ghost" aria-label="View timeline"><Clock className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="secondary">Manage</Button>
      </div>
    ),
  },
];

/** Filter-aware empty state: names the active scope and offers a one-click reset. */
function FilteredNoMatch({ entity = "records" }: { entity?: string }) {
  const { filters, clearAll } = useFilters();
  return <FilteredEmptyState entity={entity} context={filterContextLabel(filters)} onClear={clearAll} />;
}
const noMatch = <FilteredNoMatch />;

function FacilityOrdersTab({ rows }: { rows: FacilityOrder[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Facility order queue" subtitle={`${rows.length} of ${facilityOrders.length} · area/city only — no customer PII`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={orderCols} rows={rows} rowKey={(o) => o.id} empty={noMatch} onRowLabel={(o) => <StatusBadge tone={facilityOrderStatusTone[o.status]}>{o.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

/* ---------------------------- Facility assignment --------------------------- */

const facilityCols: Column<Facility>[] = [
  { key: "name", header: "Facility", primary: true, cell: (f) => <span className="font-medium text-ink">{f.name}</span> },
  { key: "area", header: "City / Area", cell: (f) => <span className="whitespace-nowrap text-ink-muted">{f.city} · {f.area}</span> },
  { key: "active", header: "Active", align: "right", cell: (f) => <span className="font-mono text-sm text-ink tnum">{f.activeOrders}</span> },
  { key: "capacity", header: "Capacity", align: "right", cell: (f) => <span className="font-mono text-sm text-ink-muted tnum">{f.capacity}</span> },
  {
    key: "load",
    header: "Load",
    cell: (f) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/8">
          <div className={cn("h-full rounded-full", f.loadPct >= 90 ? "bg-danger" : f.loadPct >= 75 ? "bg-warning" : "bg-success")} style={{ width: `${f.loadPct}%` }} />
        </div>
        <span className="font-mono text-xs text-ink-muted tnum">{f.loadPct}%</span>
      </div>
    ),
  },
  { key: "ppi", header: "PPI", align: "right", cell: (f) => <span className="font-mono text-sm text-ink tnum">{f.ppiScore}</span> },
  { key: "delayed", header: "Delayed", align: "right", cell: (f) => <span className={cn("font-mono text-sm tnum", f.delayedOrders > 0 ? "text-danger" : "text-ink-faint")}>{f.delayedOrders}</span> },
  { key: "status", header: "Status", cell: (f) => <StatusBadge tone={facilityStatusTone[f.status]}>{f.status}</StatusBadge> },
  { key: "action", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Reassign</Button> },
];

function AssignmentTab({ orders, facs }: { orders: FacilityOrder[]; facs: Facility[] }) {
  const unassigned = orders.filter((o) => o.status === "Awaiting Assignment");
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="Awaiting facility assignment" subtitle={`${unassigned.length} orders need a facility`} action={<StatusBadge tone="warning">{unassigned.length}</StatusBadge>} />
        {unassigned.length === 0 ? (
          <EmptyState icon={Building2} title="All orders assigned" description="Every order has a facility." />
        ) : (
          <ul className="space-y-2.5">
            {unassigned.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 p-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink"><span className="font-mono text-xs">{o.id}</span> · {o.service}</p>
                  <p className="flex items-center gap-1 text-xxs text-ink-muted"><MapPin className="h-3 w-3" /> {o.area} · {o.items} items</p>
                </div>
                <Button size="sm" variant="primary">Assign facility <ArrowRight className="h-3.5 w-3.5" /></Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel padded={false}>
        <PanelHeader title="Facility management" subtitle="Capacity, load and performance across the network" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={facilityCols} rows={facs} rowKey={(f) => f.name} empty={noMatch} onRowLabel={(f) => <StatusBadge tone={facilityStatusTone[f.status]}>{f.status}</StatusBadge>} />
        </div>
      </Panel>
    </div>
  );
}

/* --------------------------- Facility status updates ------------------------ */

function StatusUpdatesTab({ rows }: { rows: FacilityOrder[] }) {
  const inFlight = rows.filter((o) => o.status !== "Awaiting Assignment");
  return (
    <Panel>
      <PanelHeader title="Cleaning progress & status updates" subtitle="Move orders through the facility pipeline" />
      {inFlight.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {inFlight.map((o) => (
          <li key={o.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{o.id}</span> · {o.service} · {o.items} items</p>
              <p className="flex items-center gap-1 text-xxs text-ink-muted"><Building2 className="h-3 w-3" /> {o.facility} · {o.area}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={facilityOrderStatusTone[o.status]}>{o.status}</StatusBadge>
              <Button size="sm" variant="secondary"><RefreshCw className="h-3.5 w-3.5" /> Update status</Button>
              <Button size="sm" variant="ghost"><BadgeCheck className="h-3.5 w-3.5" /> Mark ready</Button>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ------------------------------ Facility issues ----------------------------- */

function IssuesTab({ rows }: { rows: typeof facilityIssues }) {
  if (rows.length === 0) return <Panel><PanelHeader title="Facility issues & tickets" subtitle="Operational problems raised by or for facilities" />{noMatch}</Panel>;
  return (
    <Panel>
      <PanelHeader title="Facility issues & tickets" subtitle="Operational problems raised by or for facilities" action={<StatusBadge tone="warning">{rows.filter((i) => i.status !== "Resolved").length} open</StatusBadge>} />
      <ul className="space-y-2.5">
        {rows.map((i) => (
          <li key={i.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-warning" />
              <div>
                <p className="text-sm text-ink"><span className="font-medium">{i.facility}</span> <span className="font-mono text-xxs text-ink-faint">· {i.id}</span></p>
                <p className="text-xs text-ink-muted">{i.issue} · raised {formatRelativeTime(i.raisedAt)}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 sm:pl-0">
              <StatusBadge tone={severityTone[i.severity]} dot={false}>{i.severity}</StatusBadge>
              <StatusBadge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"}>{i.status}</StatusBadge>
              <Button size="sm" variant="secondary">Manage</Button>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ------------------------------- Quality checks ----------------------------- */

function QualityTab({ rows }: { rows: QualityCheck[] }) {
  return (
    <Panel>
      <PanelHeader title="Quality checks" subtitle="Sign off before delivery handoff" action={<StatusBadge tone="plum">{rows.filter((q) => q.result === "Pending").length} pending</StatusBadge>} />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((q) => (
          <li key={q.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div>
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{q.orderId}</span> · {q.service}</p>
                <p className="flex items-center gap-1 text-xxs text-ink-muted"><MapPin className="h-3 w-3" /> {q.area} · {q.facility}</p>
                <p className="mt-0.5 text-xxs text-ink-faint">{q.note}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 sm:pl-0">
              <StatusBadge tone={qualityTone[q.result]}>{q.result}</StatusBadge>
              {q.result === "Pending" ? (
                <>
                  <Button size="sm" variant="primary">Pass</Button>
                  <Button size="sm" variant="danger">Fail</Button>
                </>
              ) : (
                <Button size="sm" variant="ghost">View</Button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ------------------------------ Delivery handoff ---------------------------- */

function HandoffTab({ rows }: { rows: HandoffOrder[] }) {
  return (
    <Panel>
      <PanelHeader title="Delivery handoff" subtitle="Ready orders passed from facility to delivery" />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((h) => (
          <li key={h.orderId} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 p-3.5">
            <div className="flex items-start gap-3">
              <Truck className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div>
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{h.orderId}</span> · {h.facility}</p>
                <p className="flex items-center gap-1 text-xxs text-ink-muted"><MapPin className="h-3 w-3" /> {h.area} · ready {formatRelativeTime(h.readyAt)}{h.driver ? ` · ${h.driver}` : ""}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge tone={handoffTone[h.status]}>{h.status}</StatusBadge>
              {h.status === "Ready" && <Button size="sm" variant="primary">Assign driver</Button>}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function FacilityFacing() {
  const { filters } = useFilters();
  const fOrders = filterFacilityOrders(facilityOrders, filters);
  const fFacilities = filterFacilities(facilities, filters);
  const fQuality = filterByArea(qualityChecks, filters);
  const fHandoff = filterByArea(deliveryHandoff, filters);
  const fIssues = applyGlobalFilters(facilityIssues, filters);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: TabDef[] = [
    { id: "orders", label: "Facility Orders", icon: <Boxes className="h-4 w-4" />, content: <FacilityOrdersTab rows={fOrders} /> },
    { id: "assign", label: "Facility Assignment", icon: <Building2 className="h-4 w-4" />, badge: fOrders.filter((o) => o.status === "Awaiting Assignment").length, content: <AssignmentTab orders={fOrders} facs={fFacilities} /> },
    { id: "status", label: "Status Updates", icon: <RefreshCw className="h-4 w-4" />, content: <StatusUpdatesTab rows={fOrders} /> },
    { id: "issues", label: "Issues", icon: <AlertTriangle className="h-4 w-4" />, badge: fIssues.filter((i) => i.status !== "Resolved").length, content: <IssuesTab rows={fIssues} /> },
    { id: "quality", label: "Quality Checks", icon: <ShieldCheck className="h-4 w-4" />, badge: fQuality.filter((q) => q.result === "Pending").length, content: <QualityTab rows={fQuality} /> },
    { id: "handoff", label: "Delivery Handoff", icon: <Truck className="h-4 w-4" />, content: <HandoffTab rows={fHandoff} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Facility snapshot</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={facilityFacingKpis} cols="4" />
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <Tabs tabs={tabs} />
        </div>
        <aside className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <div>
              <p className="text-xs font-semibold text-ink">Privacy firewall on</p>
              <p className="text-xxs text-ink-muted">Facility views show area/city only — no customer name, phone, email or full address.</p>
            </div>
          </div>
          <Panel>
            <PanelHeader title="Facility activity" subtitle="Latest facility-side events" />
            <ActivityTimeline events={facilityActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Facility actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Assign Facility", icon: Building2 },
                { label: "Reassign", icon: RefreshCw },
                { label: "Update Status", icon: RefreshCw },
                { label: "Quality Pending", icon: ShieldCheck },
                { label: "Mark Ready", icon: BadgeCheck },
                { label: "Raise Issue", icon: AlertTriangle },
                { label: "View Timeline", icon: Clock },
                { label: "Handoff Delivery", icon: Truck },
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
