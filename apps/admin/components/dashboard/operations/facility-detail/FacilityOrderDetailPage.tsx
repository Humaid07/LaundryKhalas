"use client";

import {
  Boxes, GitBranch, ShieldCheck, Building2, RefreshCw, BadgeCheck, XCircle,
  Clock, AlertTriangle, Truck, StickyNote, Gauge,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  facilityOrderStatusTone, facilityPriorityTone, qualityTone, type FacilityOrder,
} from "@/lib/dashboard/operations-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { FACILITY_LIFECYCLE } from "./data";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

function ProgressCard({ order }: { order: FacilityOrder }) {
  const currentIdx = FACILITY_LIFECYCLE.indexOf(order.status);
  return (
    <DetailSectionCard title="Cleaning progress" icon={GitBranch}>
      {order.status === "Delayed" ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/8 px-3.5 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <p className="text-sm text-danger">Delayed at facility — beyond expected completion. Review handoff / capacity.</p>
        </div>
      ) : (
        <ol className="space-y-3">
          {FACILITY_LIFECYCLE.map((s, i) => {
            const done = currentIdx >= 0 && i <= currentIdx;
            const current = s === order.status;
            return (
              <li key={s} className="flex gap-3">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${done ? "bg-rose" : "bg-ink-faint/40"}`} />
                <div className="min-w-0">
                  <p className="text-sm text-ink">{s}</p>
                  {current && <p className="text-xxs text-ink-faint">Current stage</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </DetailSectionCard>
  );
}

const ACTIONS = (o: FacilityOrder): MenuItem[] => [
  { label: "Assign facility", icon: Building2, disabled: o.status !== "Awaiting Assignment" },
  { label: "Update status", icon: RefreshCw },
  { label: "Mark ready", icon: BadgeCheck },
  { label: "Pass QC", icon: ShieldCheck, disabled: o.quality !== "Pending" },
  { label: "Fail QC", icon: XCircle, tone: "danger", disabled: o.quality !== "Pending" },
  { label: "Flag delay", icon: Clock },
  { label: "Raise issue", icon: AlertTriangle },
  { label: "Add note", icon: StickyNote },
  { label: "Handoff to delivery", icon: Truck },
];

export function FacilityOrderDetailPage({ order, backHref }: { order: FacilityOrder; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Facility Facing"
      eyebrow="Facility order"
      title={<span className="font-mono">{order.id}</span>}
      status={
        <>
          <StatusBadge tone={facilityOrderStatusTone[order.status]} dot={false}>{order.status}</StatusBadge>
          <StatusBadge tone={facilityPriorityTone[order.priority]} dot={false}>{order.priority}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(order)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Facility order" icon={Boxes}>
              <FieldGrid>
                <Field label="Order" value={order.id} mono />
                <Field label="Service" value={order.service} />
                <Field label="Items" value={order.items} />
                <Field label="Area / City" value={order.area} />
                <Field label="Pickup received" value={fmtTime(order.pickupReceived)} />
                <Field label="Expected completion" value={fmtTime(order.expectedCompletion)} />
              </FieldGrid>
            </DetailSectionCard>
            <ProgressCard order={order} />
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Assignment" icon={Building2}>
              <FieldGrid cols={2}>
                <Field label="Facility" value={order.facility || "Unassigned"} />
                <Field label="Priority" value={<Chip tone={facilityPriorityTone[order.priority]}>{order.priority}</Chip>} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Quality check" icon={Gauge}>
              <div className="flex items-center justify-between">
                <span className="text-sm text-ink-muted">Result</span>
                <Chip tone={qualityTone[order.quality]}>{order.quality}</Chip>
              </div>
            </DetailSectionCard>
            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Facility view — area/city only. No customer name, phone, email, full address or payment details.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
