"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ClipboardList, MapPin } from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterOrders, activeFilterCount } from "@/lib/dashboard/filters";
import { orderStatusTone, paymentTone } from "@/lib/dashboard/status-maps";
import { orders } from "@/lib/dashboard/mock-data";
import { customerOrdersKpis, nextStepByStatus, orderSla } from "@/lib/dashboard/operations-data";
import { formatCurrency } from "@/lib/dashboard/formatters";
import type { Order } from "@/lib/dashboard/types";
import { WorkflowTabs, CardGrid, RecordCard, Badge, maskPhone, type WorkflowTab } from "./workspace/Workspace";

const money = (n: number) => formatCurrency(n);

/* Workflow/status tabs — STATUS filters for the Customer Orders page, NOT
 * navigation to another subsection (that lives only in the sidebar). Clicking a
 * card opens the dedicated full-page detail route, not a drawer. */
type TabId =
  | "all" | "new" | "active" | "pickup" | "cleaning" | "ready"
  | "out" | "completed" | "cancelled" | "issues";

const TAB_FILTERS: Record<TabId, (o: Order) => boolean> = {
  all: () => true,
  new: (o) => o.status === "New",
  active: (o) => o.status !== "Delivered" && o.status !== "Cancelled",
  pickup: (o) => o.status === "Pickup Scheduled",
  cleaning: (o) => o.status === "In Cleaning",
  ready: (o) => o.status === "Ready for Delivery",
  out: (o) => o.status === "Out for Delivery",
  completed: (o) => o.status === "Delivered",
  cancelled: (o) => o.status === "Cancelled",
  issues: (o) => o.status === "Concern Raised",
};

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "all", label: "All Orders" },
  { id: "new", label: "New Orders" },
  { id: "active", label: "Active Orders" },
  { id: "pickup", label: "Pickup Scheduled" },
  { id: "cleaning", label: "In Cleaning" },
  { id: "ready", label: "Ready for Delivery" },
  { id: "out", label: "Out for Delivery" },
  { id: "completed", label: "Completed" },
  { id: "cancelled", label: "Cancelled" },
  { id: "issues", label: "Issues / Escalations" },
];

const isTabId = (v: string | null): v is TabId => !!v && v in TAB_FILTERS;

function itemsSummary(o: Order): string {
  const total = o.items.reduce((s, i) => s + i.qty, 0);
  return `${total} item${total === 1 ? "" : "s"}`;
}

export function CustomerOrders() {
  const router = useRouter();
  const search = useSearchParams();
  const { filters } = useFilters();
  const initialTab = search.get("tab");
  const [tab, setTab] = useState<TabId>(isTabId(initialTab) ? initialTab : "all");

  const base = useMemo(() => filterOrders(orders, filters), [filters]);
  const rows = base.filter(TAB_FILTERS[tab]);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({
    id: t.id,
    label: t.label,
    count: base.filter(TAB_FILTERS[t.id]).length,
  }));

  const openOrder = (o: Order) => router.push(`/operations/customer-orders/${o.id}?tab=${tab}`);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Order center snapshot</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={customerOrdersKpis} cols="auto" />
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>

      <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />

      {rows.length === 0 ? (
        <EmptyState icon={ClipboardList} title="No orders in this view" description="No orders match this status and the active filters." />
      ) : (
        <CardGrid>
          {rows.map((o) => (
            <RecordCard
              key={o.id}
              id={o.id}
              title={o.customer}
              onClick={() => openOrder(o)}
              badges={
                <>
                  <Badge tone={orderStatusTone[o.status]}>{o.status}</Badge>
                  <Badge tone={paymentTone[o.payment]}>{o.payment}</Badge>
                </>
              }
              fields={[
                { label: "Service", value: o.service },
                { label: "Items", value: itemsSummary(o) },
                { label: "Pickup", value: o.pickupSlot },
                { label: "City / Area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{o.city}</span> },
                { label: "Facility", value: o.facility || "—" },
                { label: "Driver", value: o.driver ?? "Unassigned" },
                { label: "Phone", value: maskPhone(o.phone) },
                { label: "Amount", value: money(o.amount) },
              ]}
              footer={
                <span className="flex items-center justify-between">
                  <span>Next: {nextStepByStatus[o.status] ?? "—"}</span>
                  <Badge tone={orderSla(o.status).tone}>{orderSla(o.status).label}</Badge>
                </span>
              }
            />
          ))}
        </CardGrid>
      )}
    </div>
  );
}
