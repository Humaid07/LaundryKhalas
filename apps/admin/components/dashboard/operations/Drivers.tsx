"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { PackageOpen, PackageCheck, AlertTriangle, MapPin, Star, SearchX } from "lucide-react";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterDrivers, filterByArea, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { priorityTone } from "@/lib/dashboard/status-maps";
import {
  drivers, pickupQueue, deliveryQueue, driverIssues,
  driverStatusTone, pickupStatusTone, deliveryStatusTone, facilityPriorityTone, paymentStatusTone,
  type PickupJob, type DeliveryJob,
} from "@/lib/dashboard/operations-data";
import { driverSlug } from "./driver-detail/data";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, EmptyState, StatusBadge,
  SnapshotBadge, type MinimalKpi, type WorkflowTab,
} from "@/components/dashboard/minimal";

/* Drivers subsection — driver-centric. Top tabs are pickup/delivery/driver
 * WORKFLOW views for THIS page only (never navigation). The driver is the
 * primary record: clicking a driver opens their full detail page (tasks +
 * actions). Task queues are light previews that open the assigned driver.
 * PRIVACY: rows show customer AREA/CITY only. */

type TabId =
  | "overview" | "pickupQueue" | "pickupScheduled" | "inTransit"
  | "deliveryQueue" | "outForDelivery" | "completed" | "issues";

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Drivers" },
  { id: "pickupQueue", label: "Pickup Queue" },
  { id: "pickupScheduled", label: "Scheduled" },
  { id: "inTransit", label: "In Transit" },
  { id: "deliveryQueue", label: "Delivery Queue" },
  { id: "outForDelivery", label: "Out for Delivery" },
  { id: "completed", label: "Completed" },
  { id: "issues", label: "Issues" },
];

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

/** Task cards open the assigned driver's detail page; unassigned tasks stay as static previews. */
const driverHref = (name: string | null, tab: string) =>
  name ? `/operations/drivers/${driverSlug(name)}?tab=${tab}` : undefined;

export function Drivers() {
  const router = useRouter();
  const { filters } = useFilters();
  const [tab, setTab] = useState<TabId>("overview");

  const fDrivers = useMemo(() => filterDrivers(drivers, filters), [filters]);
  const fPickups = useMemo(() => filterByArea(pickupQueue, filters), [filters]);
  const fDeliveries = useMemo(() => filterByArea(deliveryQueue, filters), [filters]);
  const fIssues = useMemo(() => applyGlobalFilters(driverIssues, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "Drivers online", value: String(fDrivers.filter((d) => d.status === "Online").length), tone: "success" },
    { label: "Pickups queued", value: String(fPickups.length) },
    { label: "Deliveries queued", value: String(fDeliveries.length) },
    { label: "Open issues", value: String(fIssues.filter((i) => i.status !== "Resolved").length), tone: "danger" },
  ];

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
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />

      <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs leading-relaxed text-ink-muted">
          <span className="font-semibold text-ink">Privacy firewall on.</span> Driver views show customer area/city only — no customer name, phone, email or full address.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />
        <SnapshotBadge active={isFiltered} />
      </div>

      <div className="rounded-xl border border-border/70 bg-surface px-3 py-2.5">
        <FilterBar />
      </div>

      {tab === "overview" ? (
        fDrivers.length === 0 ? (
          <EmptyState icon={SearchX} title="No drivers in this view" description="No drivers match the active filters." />
        ) : (
          <RecordList>
            {fDrivers.map((d) => (
              <CompactRecordCard
                key={d.name}
                title={d.name}
                status={{ label: d.status, tone: driverStatusTone[d.status] }}
                fields={[
                  { label: "Zone", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.zone}</span> },
                  { label: "Assigned", value: d.assignedOrders },
                  { label: "Done today", value: d.completedToday },
                ]}
                meta={<span className="inline-flex items-center gap-1 text-sm font-medium text-ink"><Star className="h-3 w-3 text-warning" />{d.rating.toFixed(1)}</span>}
                onClick={() => router.push(`/operations/drivers/${driverSlug(d.name)}?tab=overview`)}
              />
            ))}
          </RecordList>
        )
      ) : tab === "issues" ? (
        fIssues.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="No driver issues" description="Pickup/delivery problems needing ops action appear here." />
        ) : (
          <RecordList>
            {fIssues.map((i) => (
              <CompactRecordCard
                key={i.id}
                id={i.id}
                title={i.issueType}
                status={{ label: i.priority, tone: priorityTone[i.priority] }}
                fields={[
                  { label: "Driver", value: i.driver },
                  { label: "Order", value: <span className="font-mono">{i.orderId}</span> },
                  { label: "Action", value: i.actionNeeded },
                ]}
                meta={<StatusBadge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"} dot={false}>{i.status}</StatusBadge>}
                href={driverHref(i.driver !== "Unassigned" ? i.driver : null, "issues")}
              />
            ))}
          </RecordList>
        )
      ) : PICKUP_TAB[tab] ? (
        pickupRows.length === 0 ? (
          <EmptyState icon={PackageOpen} title="No pickups in this view" description="No pickups match this status and the active filters." />
        ) : (
          <RecordList>
            {pickupRows.map((p) => (
              <CompactRecordCard
                key={p.orderId}
                id={p.orderId}
                title={p.service}
                status={{ label: p.status, tone: pickupStatusTone[p.status] }}
                fields={[
                  { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
                  { label: "Pickup slot", value: p.pickupSlot },
                  { label: "Driver", value: p.driver ?? "Unassigned" },
                ]}
                meta={<StatusBadge tone={facilityPriorityTone[p.priority]} dot={false}>{p.priority}</StatusBadge>}
                href={driverHref(p.driver, "pickupQueue")}
              />
            ))}
          </RecordList>
        )
      ) : (
        deliveryRows.length === 0 ? (
          <EmptyState icon={PackageCheck} title="No deliveries in this view" description="No deliveries match this status and the active filters." />
        ) : (
          <RecordList>
            {deliveryRows.map((d) => (
              <CompactRecordCard
                key={d.orderId}
                id={d.orderId}
                title={d.service}
                status={{ label: d.status, tone: deliveryStatusTone[d.status] }}
                fields={[
                  { label: "Customer area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.area}</span> },
                  { label: "Delivery slot", value: d.deliverySlot },
                  { label: "Driver", value: d.driver ?? "Unassigned" },
                ]}
                meta={<StatusBadge tone={paymentStatusTone[d.paymentStatus] ?? "neutral"} dot={false}>{d.paymentStatus}</StatusBadge>}
                href={driverHref(d.driver, "deliveryQueue")}
              />
            ))}
          </RecordList>
        )
      )}
    </div>
  );
}
