"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ClipboardList } from "lucide-react";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterOrders, activeFilterCount } from "@/lib/dashboard/filters";
import { orderStatusTone } from "@/lib/dashboard/status-maps";
import { orders } from "@/lib/dashboard/mock-data";
import { nextStepByStatus, orderSla } from "@/lib/dashboard/operations-data";
import type { Order } from "@/lib/dashboard/types";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, EmptyState, StatusBadge,
  SnapshotBadge, type MinimalKpi, type WorkflowTab,
} from "@/components/dashboard/minimal";

/* Workflow/status tabs — STATUS filters for the Customer Orders page, NOT
 * navigation to another subsection (that lives only in the sidebar). Clicking a
 * card opens the dedicated full-page detail route — never a drawer. Only a light
 * preview shows here; the detail page carries the full record and all actions. */
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
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "new", label: "New" },
  { id: "pickup", label: "Pickup" },
  { id: "cleaning", label: "In Cleaning" },
  { id: "ready", label: "Ready" },
  { id: "out", label: "Out for Delivery" },
  { id: "completed", label: "Completed" },
  { id: "issues", label: "Issues" },
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
  const [tab, setTab] = useState<TabId>(isTabId(initialTab) ? initialTab : "active");

  const base = useMemo(() => filterOrders(orders, filters), [filters]);
  const rows = base.filter(TAB_FILTERS[tab]);
  const isFiltered = activeFilterCount(filters) > 0;

  // Compact, curated KPI row — the deeper metric set lives on the Overview page.
  const kpis: MinimalKpi[] = [
    { label: "Active orders", value: String(base.filter(TAB_FILTERS.active).length) },
    { label: "In cleaning", value: String(base.filter(TAB_FILTERS.cleaning).length) },
    { label: "Ready for delivery", value: String(base.filter(TAB_FILTERS.ready).length) },
    { label: "Needs attention", value: String(base.filter(TAB_FILTERS.issues).length), tone: "danger" },
  ];

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({
    id: t.id,
    label: t.label,
    count: base.filter(TAB_FILTERS[t.id]).length,
  }));

  const openOrder = (o: Order) => router.push(`/operations/customer-orders/${o.id}?tab=${tab}`);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />
        <SnapshotBadge active={isFiltered} />
      </div>

      <div className="rounded-xl border border-border/70 bg-surface px-3 py-2.5">
        <FilterBar />
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={ClipboardList} title="No orders in this view" description="No orders match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((o) => (
            <CompactRecordCard
              key={o.id}
              id={o.id}
              title={o.customer}
              status={{ label: o.status, tone: orderStatusTone[o.status] }}
              fields={[
                { label: "Service", value: o.service },
                { label: "Items", value: itemsSummary(o) },
                { label: "Pickup", value: o.pickupSlot },
              ]}
              meta={
                <span className="flex flex-col items-end gap-1">
                  <StatusBadge tone={orderSla(o.status).tone} dot={false}>{orderSla(o.status).label}</StatusBadge>
                  <span className="hidden text-xxs text-ink-faint sm:block">Next: {nextStepByStatus[o.status] ?? "—"}</span>
                </span>
              }
              onClick={() => openOrder(o)}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}
