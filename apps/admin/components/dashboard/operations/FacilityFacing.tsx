"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Boxes, ShieldCheck, AlertTriangle, Truck, MapPin } from "lucide-react";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterFacilityOrders, filterByArea, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import {
  facilityOrders, facilityIssues, deliveryHandoff,
  facilityOrderStatusTone, facilityPriorityTone, severityTone, handoffTone,
  type FacilityOrder,
} from "@/lib/dashboard/operations-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, EmptyState, StatusBadge,
  SnapshotBadge, type MinimalKpi, type WorkflowTab,
} from "@/components/dashboard/minimal";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

type TabId = "all" | "awaiting" | "cleaning" | "qc" | "delayed" | "ready" | "issues" | "handoffs";

const ORDER_TAB_FILTERS: Partial<Record<TabId, (o: FacilityOrder) => boolean>> = {
  all: () => true,
  awaiting: (o) => o.status === "Awaiting Assignment",
  cleaning: (o) => o.status === "In Cleaning",
  qc: (o) => o.status === "Quality Check",
  delayed: (o) => o.status === "Delayed",
  ready: (o) => o.status === "Ready for Delivery",
};

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "awaiting", label: "Awaiting" },
  { id: "cleaning", label: "In Cleaning" },
  { id: "qc", label: "Quality Check" },
  { id: "delayed", label: "Delayed" },
  { id: "ready", label: "Ready" },
  { id: "issues", label: "Issues" },
  { id: "handoffs", label: "Handoffs" },
];

export function FacilityFacing() {
  const router = useRouter();
  const { filters } = useFilters();
  const [tab, setTab] = useState<TabId>("all");

  const fOrders = useMemo(() => filterFacilityOrders(facilityOrders, filters), [filters]);
  const fIssues = useMemo(() => applyGlobalFilters(facilityIssues, filters), [filters]);
  const fHandoff = useMemo(() => filterByArea(deliveryHandoff, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const kpis: MinimalKpi[] = [
    { label: "In cleaning", value: String(fOrders.filter(ORDER_TAB_FILTERS.cleaning!).length) },
    { label: "QC pending", value: String(fOrders.filter(ORDER_TAB_FILTERS.qc!).length), tone: "warning" },
    { label: "Ready for delivery", value: String(fOrders.filter(ORDER_TAB_FILTERS.ready!).length), tone: "success" },
    { label: "Delayed", value: String(fOrders.filter(ORDER_TAB_FILTERS.delayed!).length), tone: "danger" },
  ];

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({
    id: t.id,
    label: t.label,
    count:
      t.id === "issues" ? fIssues.length
      : t.id === "handoffs" ? fHandoff.length
      : fOrders.filter(ORDER_TAB_FILTERS[t.id]!).length,
  }));

  const orderRows = tab !== "issues" && tab !== "handoffs" ? fOrders.filter(ORDER_TAB_FILTERS[tab]!) : [];
  const openOrder = (o: FacilityOrder) => router.push(`/operations/facility-facing/orders/${o.id}?tab=${tab}`);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />

      <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs leading-relaxed text-ink-muted">
          <span className="font-semibold text-ink">Privacy firewall on.</span> Facility views show area/city only — no customer name, phone, email, full address or payment details.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />
        <SnapshotBadge active={isFiltered} />
      </div>

      <div className="rounded-xl border border-border/70 bg-surface px-3 py-2.5">
        <FilterBar />
      </div>

      {tab === "issues" ? (
        fIssues.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="No facility issues" description="Operational problems raised by or for facilities appear here." />
        ) : (
          <RecordList>
            {fIssues.map((i) => (
              <CompactRecordCard
                key={i.id}
                id={i.id}
                title={i.facility}
                status={{ label: i.severity, tone: severityTone[i.severity] }}
                fields={[
                  { label: "City", value: i.city },
                  { label: "Raised", value: formatRelativeTime(i.raisedAt) },
                  { label: "Issue", value: i.issue },
                ]}
                meta={<StatusBadge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"} dot={false}>{i.status}</StatusBadge>}
              />
            ))}
          </RecordList>
        )
      ) : tab === "handoffs" ? (
        fHandoff.length === 0 ? (
          <EmptyState icon={Truck} title="No handoffs" description="Ready orders passed from facility to delivery appear here." />
        ) : (
          <RecordList>
            {fHandoff.map((h) => (
              <CompactRecordCard
                key={h.orderId}
                id={h.orderId}
                title={h.facility}
                status={{ label: h.status, tone: handoffTone[h.status] }}
                fields={[
                  { label: "Area / City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{h.area}</span> },
                  { label: "Driver", value: h.driver ?? "Unassigned" },
                  { label: "Ready", value: formatRelativeTime(h.readyAt) },
                ]}
                href={`/operations/customer-orders/${h.orderId}`}
              />
            ))}
          </RecordList>
        )
      ) : orderRows.length === 0 ? (
        <EmptyState icon={Boxes} title="No facility orders in this view" description="No orders match this status and the active filters." />
      ) : (
        <RecordList>
          {orderRows.map((o) => (
            <CompactRecordCard
              key={o.id}
              id={o.id}
              title={o.service}
              status={{ label: o.status, tone: facilityOrderStatusTone[o.status] }}
              fields={[
                { label: "Facility", value: o.facility || "Unassigned" },
                { label: "Items", value: o.items },
                { label: "Area / City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{o.area}</span> },
              ]}
              meta={
                <span className="flex flex-col items-end gap-1">
                  <StatusBadge tone={facilityPriorityTone[o.priority]} dot={false}>{o.priority}</StatusBadge>
                  <span className="hidden text-xxs text-ink-faint sm:block">Exp: {fmtTime(o.expectedCompletion)}</span>
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
