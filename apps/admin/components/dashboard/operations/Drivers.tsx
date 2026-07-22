"use client";

import { useMemo, useState } from "react";
import {
  UserRound, PackageOpen, PackageCheck, AlertTriangle, MapPin, Truck, Route,
  Phone, Play, Check, RefreshCw, Clock, StickyNote, ArrowUpRight, Star, SearchX,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterDrivers, filterByArea, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { priorityTone } from "@/lib/dashboard/status-maps";
import {
  driverKpis, drivers, pickupQueue, deliveryQueue, driverIssues,
  driverStatusTone, pickupStatusTone, deliveryStatusTone, facilityPriorityTone, paymentStatusTone,
  type Driver, type PickupJob, type DeliveryJob, type DriverIssue,
} from "@/lib/dashboard/operations-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import {
  WorkflowTabs, CardGrid, RecordCard, DetailDrawer, DetailFields, DrawerSection,
  DrawerActions, Badge, type WorkflowTab, type DrawerAction,
} from "./workspace/Workspace";

/* ============================================================================
 * Drivers subsection. Top tabs are pickup/delivery/driver WORKFLOW views for
 * THIS page only — never navigation to another Operations subsection (that lives
 * in the left sidebar). Cards are clickable; every action lives inside the
 * DetailDrawer for the selected record. See docs/architecture/operations-navigation.md.
 *
 * PRIVACY: driver-facing rows show customer AREA/CITY only — never customer name,
 * phone, email or full street address.
 * ========================================================================== */

type TabId =
  | "overview" | "pickupQueue" | "pickupScheduled" | "inTransit"
  | "deliveryQueue" | "outForDelivery" | "completed" | "issues";

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Driver Overview" },
  { id: "pickupQueue", label: "Pickup Queue" },
  { id: "pickupScheduled", label: "Pickup Scheduled" },
  { id: "inTransit", label: "In Transit to Facility" },
  { id: "deliveryQueue", label: "Delivery Queue" },
  { id: "outForDelivery", label: "Out for Delivery" },
  { id: "completed", label: "Completed Deliveries" },
  { id: "issues", label: "Driver Issues" },
];

/* Status → tab filters (deterministic split of existing pickup/delivery data). */
const PICKUP_TAB: Partial<Record<TabId, (p: PickupJob) => boolean>> = {
  pickupQueue: () => true,
  pickupScheduled: (p) => p.status === "Driver Assigned" || p.status === "Awaiting Driver",
  inTransit: (p) => p.status === "Picked Up",
};
const DELIVERY_TAB: Partial<Record<TabId, (d: DeliveryJob) => boolean>> = {
  deliveryQueue: () => true,
  outForDelivery: (d) => d.status === "En Route to Customer" || d.status === "Driver Assigned",
  completed: (d) => d.status === "Delivered",
};

/* -------------------------------- Detail bodies ----------------------------- */

function DriverDetail({ d }: { d: Driver }) {
  return (
    <DrawerSection title="Driver">
      <DetailFields
        fields={[
          { label: "Name", value: d.name },
          { label: "Status", value: <Badge tone={driverStatusTone[d.status]}>{d.status}</Badge> },
          { label: "Zone", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.zone}</span> },
          { label: "Assigned orders", value: d.assignedOrders },
          { label: "Completed today", value: d.completedToday },
          { label: "Delayed jobs", value: d.delayedJobs },
          { label: "Rating", value: <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 text-warning" />{d.rating.toFixed(1)}</span> },
          { label: "PPI score", value: d.ppiScore },
          { label: "Last active", value: formatRelativeTime(d.lastActive) },
        ]}
      />
    </DrawerSection>
  );
}

function PickupDetail({ p }: { p: PickupJob }) {
  return (
    <>
      <DrawerSection title="Pickup task">
        <DetailFields
          fields={[
            { label: "Order", value: <span className="font-mono">{p.orderId}</span> },
            { label: "Service", value: p.service },
            { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
            { label: "Pickup slot", value: p.pickupSlot },
            { label: "Driver", value: p.driver ?? "Unassigned" },
            { label: "Status", value: <Badge tone={pickupStatusTone[p.status]}>{p.status}</Badge> },
            { label: "Priority", value: <Badge tone={facilityPriorityTone[p.priority]}>{p.priority}</Badge> },
          ]}
        />
      </DrawerSection>
      <DrawerSection title="Notes">
        <p className="text-sm text-ink">{p.notes || "—"}</p>
      </DrawerSection>
      <DrawerSection title="Privacy">
        <p className="text-xs text-ink-muted">Driver view — customer area/city only. No customer name, phone, email or full address.</p>
      </DrawerSection>
    </>
  );
}

function DeliveryDetail({ d }: { d: DeliveryJob }) {
  return (
    <>
      <DrawerSection title="Delivery task">
        <DetailFields
          fields={[
            { label: "Order", value: <span className="font-mono">{d.orderId}</span> },
            { label: "Service", value: d.service },
            { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.area}</span> },
            { label: "Delivery slot", value: d.deliverySlot },
            { label: "Driver", value: d.driver ?? "Unassigned" },
            { label: "Facility", value: d.facility },
            { label: "Status", value: <Badge tone={deliveryStatusTone[d.status]}>{d.status}</Badge> },
            { label: "Payment", value: <Badge tone={paymentStatusTone[d.paymentStatus] ?? "neutral"}>{d.paymentStatus}</Badge> },
          ]}
        />
      </DrawerSection>
      <DrawerSection title="Privacy">
        <p className="text-xs text-ink-muted">Driver view — customer area/city only. No customer name, phone, email or full address.</p>
      </DrawerSection>
    </>
  );
}

function DriverIssueDetail({ i }: { i: DriverIssue }) {
  return (
    <DrawerSection title="Driver issue">
      <DetailFields
        fields={[
          { label: "Reference", value: <span className="font-mono">{i.id}</span> },
          { label: "Driver", value: i.driver },
          { label: "Order", value: <span className="font-mono">{i.orderId}</span> },
          { label: "City", value: i.city },
          { label: "Type", value: i.issueType },
          { label: "Priority", value: <Badge tone={priorityTone[i.priority]}>{i.priority}</Badge> },
          { label: "Status", value: i.status },
          { label: "Reported", value: formatRelativeTime(i.reportedAt) },
        ]}
      />
      <p className="mt-3 text-sm text-ink"><span className="font-semibold">Action needed:</span> {i.actionNeeded}</p>
    </DrawerSection>
  );
}

/* -------------------------------- Actions ----------------------------------- */

const DRIVER_ACTIONS = (): DrawerAction[] => [
  { label: "Assign order", icon: PackageOpen, tone: "primary" },
  { label: "Reassign driver", icon: RefreshCw },
  { label: "View route", icon: Route },
  { label: "Contact driver", icon: Phone },
  { label: "Track ETA", icon: Clock },
  { label: "Add note", icon: StickyNote },
];

const PICKUP_ACTIONS = (p: PickupJob): DrawerAction[] => [
  { label: "Assign driver", icon: UserRound, tone: "primary", disabled: !!p.driver },
  { label: "Reassign driver", icon: RefreshCw, disabled: !p.driver },
  { label: "Start pickup", icon: Play, disabled: p.status !== "Driver Assigned" },
  { label: "Mark picked up", icon: PackageCheck, disabled: p.status === "Picked Up" },
  { label: "Reschedule pickup", icon: Clock },
  { label: "View route", icon: Route },
  { label: "Contact driver", icon: Phone, disabled: !p.driver },
  { label: "Report issue", icon: AlertTriangle },
  { label: "Add note", icon: StickyNote },
];

const DELIVERY_ACTIONS = (d: DeliveryJob): DrawerAction[] => [
  { label: "Assign driver", icon: UserRound, tone: "primary", disabled: !!d.driver },
  { label: "Reassign driver", icon: RefreshCw, disabled: !d.driver },
  { label: "Start delivery", icon: Truck, disabled: d.status !== "Driver Assigned" },
  { label: "Mark delivered", icon: Check, disabled: d.status === "Delivered" },
  { label: "Reschedule delivery", icon: Clock },
  { label: "View route", icon: Route },
  { label: "Contact driver", icon: Phone, disabled: !d.driver },
  { label: "Report issue", icon: AlertTriangle },
  { label: "Add note", icon: StickyNote },
];

const ISSUE_ACTIONS = (i: DriverIssue): DrawerAction[] => [
  { label: "Reassign driver", icon: RefreshCw, tone: "primary" },
  { label: "Contact driver", icon: Phone },
  { label: "Contact customer", icon: UserRound },
  { label: "Escalate to human", icon: ArrowUpRight },
  { label: "Resolve issue", icon: Check, disabled: i.status === "Resolved" },
  { label: "Add note", icon: StickyNote },
];

const ACTION_NOTE = "Driver workflow only. Actions requiring approval are labelled; nothing is dispatched live from this view.";

/* --------------------------------- Section ---------------------------------- */

type Selected =
  | { kind: "driver"; data: Driver }
  | { kind: "pickup"; data: PickupJob }
  | { kind: "delivery"; data: DeliveryJob }
  | { kind: "issue"; data: DriverIssue }
  | null;

export function Drivers() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<TabId>("overview");
  const [selected, setSelected] = useState<Selected>(null);

  const fDrivers = useMemo(() => filterDrivers(drivers, filters), [filters]);
  const fPickups = useMemo(() => filterByArea(pickupQueue, filters), [filters]);
  const fDeliveries = useMemo(() => filterByArea(deliveryQueue, filters), [filters]);
  const fIssues = useMemo(() => applyGlobalFilters(driverIssues, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({
    id: t.id,
    label: t.label,
    count:
      t.id === "overview" ? fDrivers.length
      : t.id === "issues" ? fIssues.length
      : PICKUP_TAB[t.id] ? fPickups.filter(PICKUP_TAB[t.id]!).length
      : DELIVERY_TAB[t.id] ? fDeliveries.filter(DELIVERY_TAB[t.id]!).length
      : 0,
  }));

  const pickupRows = PICKUP_TAB[tab] ? fPickups.filter(PICKUP_TAB[tab]!) : [];
  const deliveryRows = DELIVERY_TAB[tab] ? fDeliveries.filter(DELIVERY_TAB[tab]!) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Fleet snapshot · area/city only</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={driverKpis} cols="4" />
      <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 px-3.5 py-2.5">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs text-ink-muted"><span className="font-semibold text-ink">Privacy firewall on.</span> Driver views show customer area/city only — no customer name, phone, email or full address.</p>
      </div>
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>

      <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />

      {/* Driver Overview */}
      {tab === "overview" ? (
        fDrivers.length === 0 ? (
          <EmptyState icon={SearchX} title="No drivers in this view" description="No drivers match the active filters." />
        ) : (
          <CardGrid>
            {fDrivers.map((d) => (
              <RecordCard
                key={d.name}
                title={d.name}
                onClick={() => setSelected({ kind: "driver", data: d })}
                badges={<Badge tone={driverStatusTone[d.status]}>{d.status}</Badge>}
                fields={[
                  { label: "Zone", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.zone}</span> },
                  { label: "Assigned", value: d.assignedOrders },
                  { label: "Done today", value: d.completedToday },
                  { label: "Delayed", value: d.delayedJobs },
                  { label: "Rating", value: <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 text-warning" />{d.rating.toFixed(1)}</span> },
                  { label: "PPI", value: d.ppiScore },
                ]}
                footer={<span>Last active {formatRelativeTime(d.lastActive)}</span>}
              />
            ))}
          </CardGrid>
        )
      ) : tab === "issues" ? (
        fIssues.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="No driver issues" description="Pickup/delivery problems needing ops action appear here." />
        ) : (
          <CardGrid>
            {fIssues.map((i) => (
              <RecordCard
                key={i.id}
                id={i.id}
                title={i.issueType}
                onClick={() => setSelected({ kind: "issue", data: i })}
                badges={<><Badge tone={priorityTone[i.priority]}>{i.priority}</Badge><Badge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"}>{i.status}</Badge></>}
                fields={[
                  { label: "Driver", value: i.driver },
                  { label: "Order", value: <span className="font-mono">{i.orderId}</span> },
                  { label: "City", value: i.city },
                  { label: "Reported", value: formatRelativeTime(i.reportedAt) },
                ]}
                footer={i.actionNeeded}
              />
            ))}
          </CardGrid>
        )
      ) : PICKUP_TAB[tab] ? (
        pickupRows.length === 0 ? (
          <EmptyState icon={PackageOpen} title="No pickups in this view" description="No pickups match this status and the active filters." />
        ) : (
          <CardGrid>
            {pickupRows.map((p) => (
              <RecordCard
                key={p.orderId}
                id={p.orderId}
                title={p.service}
                onClick={() => setSelected({ kind: "pickup", data: p })}
                badges={<><Badge tone={pickupStatusTone[p.status]}>{p.status}</Badge><Badge tone={facilityPriorityTone[p.priority]}>{p.priority}</Badge></>}
                fields={[
                  { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
                  { label: "Pickup slot", value: p.pickupSlot },
                  { label: "Driver", value: p.driver ?? "Unassigned" },
                ]}
                footer={p.notes || undefined}
              />
            ))}
          </CardGrid>
        )
      ) : (
        deliveryRows.length === 0 ? (
          <EmptyState icon={PackageCheck} title="No deliveries in this view" description="No deliveries match this status and the active filters." />
        ) : (
          <CardGrid>
            {deliveryRows.map((d) => (
              <RecordCard
                key={d.orderId}
                id={d.orderId}
                title={d.service}
                onClick={() => setSelected({ kind: "delivery", data: d })}
                badges={<><Badge tone={deliveryStatusTone[d.status]}>{d.status}</Badge><Badge tone={paymentStatusTone[d.paymentStatus] ?? "neutral"}>{d.paymentStatus}</Badge></>}
                fields={[
                  { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.area}</span> },
                  { label: "Delivery slot", value: d.deliverySlot },
                  { label: "Driver", value: d.driver ?? "Unassigned" },
                  { label: "Facility", value: d.facility },
                ]}
              />
            ))}
          </CardGrid>
        )
      )}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        eyebrow={
          selected?.kind === "driver" ? "Driver"
          : selected?.kind === "issue" ? "Driver issue"
          : selected?.kind === "delivery" ? "Delivery task"
          : "Pickup task"
        }
        title={selected ? (selected.kind === "driver" ? selected.data.name : selected.kind === "issue" ? selected.data.id : selected.data.orderId) : ""}
        subtitle={
          selected?.kind === "pickup" ? selected.data.service
          : selected?.kind === "delivery" ? selected.data.service
          : selected?.kind === "issue" ? selected.data.issueType
          : undefined
        }
        actions={
          selected && (
            <DrawerActions
              actions={
                selected.kind === "driver" ? DRIVER_ACTIONS()
                : selected.kind === "pickup" ? PICKUP_ACTIONS(selected.data)
                : selected.kind === "delivery" ? DELIVERY_ACTIONS(selected.data)
                : ISSUE_ACTIONS(selected.data)
              }
              note={ACTION_NOTE}
            />
          )
        }
      >
        {selected?.kind === "driver" && <DriverDetail d={selected.data} />}
        {selected?.kind === "pickup" && <PickupDetail p={selected.data} />}
        {selected?.kind === "delivery" && <DeliveryDetail d={selected.data} />}
        {selected?.kind === "issue" && <DriverIssueDetail i={selected.data} />}
      </DetailDrawer>
    </div>
  );
}
