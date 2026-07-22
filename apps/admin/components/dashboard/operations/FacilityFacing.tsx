"use client";

import { useMemo, useState } from "react";
import {
  Boxes, Building2, RefreshCw, ShieldCheck, BadgeCheck, XCircle, AlertTriangle,
  Truck, StickyNote, Clock, MapPin,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterFacilityOrders, filterByArea, applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import {
  facilityFacingKpis, facilityOrders, facilityIssues, deliveryHandoff,
  facilityOrderStatusTone, facilityPriorityTone, qualityTone, severityTone, handoffTone,
  type FacilityOrder, type FacilityIssue, type HandoffOrder,
} from "@/lib/dashboard/operations-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import {
  WorkflowTabs, CardGrid, RecordCard, DetailDrawer, DetailFields, DrawerSection,
  DrawerTimeline, DrawerActions, Badge, type WorkflowTab, type DrawerAction,
} from "./workspace/Workspace";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

const FACILITY_LIFECYCLE: FacilityOrder["status"][] = [
  "Awaiting Assignment", "In Cleaning", "Quality Check", "Ready for Delivery",
];

type TabId =
  | "all" | "awaiting" | "cleaning" | "qc" | "delayed" | "ready" | "issues" | "handoffs";

const ORDER_TAB_FILTERS: Partial<Record<TabId, (o: FacilityOrder) => boolean>> = {
  all: () => true,
  awaiting: (o) => o.status === "Awaiting Assignment",
  cleaning: (o) => o.status === "In Cleaning",
  qc: (o) => o.status === "Quality Check",
  delayed: (o) => o.status === "Delayed",
  ready: (o) => o.status === "Ready for Delivery",
};

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "all", label: "All Facility Orders" },
  { id: "awaiting", label: "Awaiting Assignment" },
  { id: "cleaning", label: "In Cleaning" },
  { id: "qc", label: "Quality Check" },
  { id: "delayed", label: "Delayed at Facility" },
  { id: "ready", label: "Ready for Delivery" },
  { id: "issues", label: "Facility Issues" },
  { id: "handoffs", label: "Handoffs" },
];

/* -------------------------------- Detail bodies ----------------------------- */

function FacilityOrderDetail({ order }: { order: FacilityOrder }) {
  const currentIdx = FACILITY_LIFECYCLE.indexOf(order.status);
  return (
    <>
      <DrawerSection title="Facility order">
        <DetailFields
          fields={[
            { label: "Order", value: <span className="font-mono">{order.id}</span> },
            { label: "Facility", value: order.facility || "Unassigned" },
            { label: "Service", value: order.service },
            { label: "Items", value: order.items },
            { label: "Area / City", value: order.area },
            { label: "Priority", value: <Badge tone={facilityPriorityTone[order.priority]}>{order.priority}</Badge> },
            { label: "Pickup received", value: fmtTime(order.pickupReceived) },
            { label: "Expected", value: fmtTime(order.expectedCompletion) },
          ]}
        />
      </DrawerSection>

      <DrawerSection title="Cleaning progress">
        {order.status === "Delayed" ? (
          <p className="text-sm text-danger">Delayed at facility — beyond expected completion. Review handoff / capacity.</p>
        ) : (
          <DrawerTimeline
            events={FACILITY_LIFECYCLE.map((s, i) => ({
              label: s,
              done: currentIdx >= 0 && i <= currentIdx,
              time: s === order.status ? "current" : undefined,
            }))}
          />
        )}
      </DrawerSection>

      <DrawerSection title="Quality check">
        <Badge tone={qualityTone[order.quality]}>{order.quality}</Badge>
      </DrawerSection>

      <DrawerSection title="Privacy">
        <p className="text-xs text-ink-muted">Facility view — area/city only. No customer name, phone, email, full address or payment details.</p>
      </DrawerSection>
    </>
  );
}

function FacilityIssueDetail({ issue }: { issue: FacilityIssue }) {
  return (
    <DrawerSection title="Facility issue">
      <DetailFields
        fields={[
          { label: "Reference", value: <span className="font-mono">{issue.id}</span> },
          { label: "Facility", value: issue.facility },
          { label: "City", value: issue.city },
          { label: "Severity", value: <Badge tone={severityTone[issue.severity]}>{issue.severity}</Badge> },
          { label: "Status", value: issue.status },
          { label: "Raised", value: formatRelativeTime(issue.raisedAt) },
        ]}
      />
      <p className="mt-3 text-sm text-ink">{issue.issue}</p>
    </DrawerSection>
  );
}

function HandoffDetail({ h }: { h: HandoffOrder }) {
  return (
    <DrawerSection title="Delivery handoff">
      <DetailFields
        fields={[
          { label: "Order", value: <span className="font-mono">{h.orderId}</span> },
          { label: "Facility", value: h.facility },
          { label: "Area / City", value: h.area },
          { label: "Driver", value: h.driver ?? "Unassigned" },
          { label: "Ready at", value: formatRelativeTime(h.readyAt) },
          { label: "Status", value: <Badge tone={handoffTone[h.status]}>{h.status}</Badge> },
        ]}
      />
    </DrawerSection>
  );
}

const FACILITY_ORDER_ACTIONS = (o: FacilityOrder): DrawerAction[] => [
  { label: "Assign facility", icon: Building2, tone: "primary", disabled: o.status !== "Awaiting Assignment" },
  { label: "Update status", icon: RefreshCw },
  { label: "Mark ready", icon: BadgeCheck },
  { label: "Pass QC", icon: ShieldCheck, disabled: o.quality !== "Pending" },
  { label: "Fail QC", icon: XCircle, tone: "danger", disabled: o.quality !== "Pending" },
  { label: "Flag delay", icon: Clock },
  { label: "Raise issue", icon: AlertTriangle },
  { label: "Add note", icon: StickyNote },
  { label: "Handoff to delivery", icon: Truck },
];

/* --------------------------------- Section ---------------------------------- */

type Selected =
  | { kind: "order"; data: FacilityOrder }
  | { kind: "issue"; data: FacilityIssue }
  | { kind: "handoff"; data: HandoffOrder }
  | null;

export function FacilityFacing() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<TabId>("all");
  const [selected, setSelected] = useState<Selected>(null);

  const fOrders = useMemo(() => filterFacilityOrders(facilityOrders, filters), [filters]);
  const fIssues = useMemo(() => applyGlobalFilters(facilityIssues, filters), [filters]);
  const fHandoff = useMemo(() => filterByArea(deliveryHandoff, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({
    id: t.id,
    label: t.label,
    count:
      t.id === "issues" ? fIssues.length
      : t.id === "handoffs" ? fHandoff.length
      : fOrders.filter(ORDER_TAB_FILTERS[t.id]!).length,
  }));

  const orderRows = tab !== "issues" && tab !== "handoffs" ? fOrders.filter(ORDER_TAB_FILTERS[tab]!) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Facility snapshot · area/city only</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={facilityFacingKpis} cols="4" />
      <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 px-3.5 py-2.5">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs text-ink-muted"><span className="font-semibold text-ink">Privacy firewall on.</span> Facility views show area/city only — no customer name, phone, email, full address or payment details.</p>
      </div>
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>

      <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />

      {tab === "issues" ? (
        fIssues.length === 0 ? <EmptyState icon={AlertTriangle} title="No facility issues" description="Operational problems raised by or for facilities appear here." /> : (
          <CardGrid>
            {fIssues.map((i) => (
              <RecordCard
                key={i.id}
                id={i.id}
                title={i.facility}
                onClick={() => setSelected({ kind: "issue", data: i })}
                badges={<><Badge tone={severityTone[i.severity]}>{i.severity}</Badge><Badge tone={i.status === "Resolved" ? "success" : i.status === "Investigating" ? "info" : "warning"}>{i.status}</Badge></>}
                fields={[
                  { label: "City", value: i.city },
                  { label: "Raised", value: formatRelativeTime(i.raisedAt) },
                ]}
                footer={i.issue}
              />
            ))}
          </CardGrid>
        )
      ) : tab === "handoffs" ? (
        fHandoff.length === 0 ? <EmptyState icon={Truck} title="No handoffs" description="Ready orders passed from facility to delivery appear here." /> : (
          <CardGrid>
            {fHandoff.map((h) => (
              <RecordCard
                key={h.orderId}
                id={h.orderId}
                title={h.facility}
                onClick={() => setSelected({ kind: "handoff", data: h })}
                badges={<Badge tone={handoffTone[h.status]}>{h.status}</Badge>}
                fields={[
                  { label: "Area / City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{h.area}</span> },
                  { label: "Driver", value: h.driver ?? "Unassigned" },
                  { label: "Ready", value: formatRelativeTime(h.readyAt) },
                ]}
              />
            ))}
          </CardGrid>
        )
      ) : orderRows.length === 0 ? (
        <EmptyState icon={Boxes} title="No facility orders in this view" description="No orders match this status and the active filters." />
      ) : (
        <CardGrid>
          {orderRows.map((o) => (
            <RecordCard
              key={o.id}
              id={o.id}
              title={o.service}
              onClick={() => setSelected({ kind: "order", data: o })}
              badges={<><Badge tone={facilityOrderStatusTone[o.status]}>{o.status}</Badge><Badge tone={facilityPriorityTone[o.priority]}>{o.priority}</Badge></>}
              fields={[
                { label: "Facility", value: o.facility || "Unassigned" },
                { label: "Items", value: o.items },
                { label: "Area / City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{o.area}</span> },
                { label: "Expected", value: fmtTime(o.expectedCompletion) },
                { label: "QC", value: <Badge tone={qualityTone[o.quality]}>{o.quality}</Badge> },
              ]}
            />
          ))}
        </CardGrid>
      )}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        eyebrow={selected?.kind === "issue" ? "Facility issue" : selected?.kind === "handoff" ? "Delivery handoff" : "Facility order"}
        title={selected ? (selected.kind === "order" ? selected.data.id : selected.kind === "issue" ? selected.data.facility : selected.data.orderId) : ""}
        subtitle={selected?.kind === "order" ? `${selected.data.service} · ${selected.data.items} items` : undefined}
        actions={selected?.kind === "order" && <DrawerActions actions={FACILITY_ORDER_ACTIONS(selected.data)} note="Facility workflow only. Nothing is dispatched live from this view." />}
      >
        {selected?.kind === "order" && <FacilityOrderDetail order={selected.data} />}
        {selected?.kind === "issue" && <FacilityIssueDetail issue={selected.data} />}
        {selected?.kind === "handoff" && <HandoffDetail h={selected.data} />}
      </DetailDrawer>
    </div>
  );
}
