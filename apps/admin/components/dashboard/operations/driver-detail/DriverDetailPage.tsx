"use client";

import {
  UserRound, MapPin, Star, PackageOpen, PackageCheck, AlertTriangle, ShieldCheck,
  RefreshCw, Route, Phone, Clock, StickyNote,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  driverStatusTone, pickupStatusTone, deliveryStatusTone,
  paymentStatusTone,
} from "@/lib/dashboard/operations-data";
import { priorityTone } from "@/lib/dashboard/status-maps";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { DriverWithTasks } from "./data";

const ACTIONS: MenuItem[] = [
  { label: "Assign order", icon: PackageOpen },
  { label: "Reassign tasks", icon: RefreshCw },
  { label: "View route", icon: Route },
  { label: "Contact driver", icon: Phone },
  { label: "Track ETA", icon: Clock },
  { label: "Add note", icon: StickyNote },
];

export function DriverDetailPage({ data, backHref }: { data: DriverWithTasks; backHref: string }) {
  const { driver: d, pickups, deliveries, issues } = data;
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Drivers"
      eyebrow="Driver"
      title={d.name}
      status={<StatusBadge tone={driverStatusTone[d.status]} dot={false}>{d.status}</StatusBadge>}
      actions={<ActionMenu items={ACTIONS} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Pickup tasks" icon={PackageOpen}>
              {pickups.length === 0 ? (
                <p className="text-sm text-ink-muted">No pickup tasks assigned.</p>
              ) : (
                <ul className="space-y-3">
                  {pickups.map((p) => (
                    <li key={p.orderId} className="flex items-center justify-between gap-3 border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="font-mono text-xs font-semibold text-rose">{p.orderId}</p>
                        <p className="truncate text-sm text-ink">{p.service}</p>
                        <p className="text-xxs text-ink-faint">{p.area} · {p.pickupSlot}</p>
                      </div>
                      <StatusBadge tone={pickupStatusTone[p.status]} dot={false}>{p.status}</StatusBadge>
                    </li>
                  ))}
                </ul>
              )}
            </DetailSectionCard>

            <DetailSectionCard title="Delivery tasks" icon={PackageCheck}>
              {deliveries.length === 0 ? (
                <p className="text-sm text-ink-muted">No delivery tasks assigned.</p>
              ) : (
                <ul className="space-y-3">
                  {deliveries.map((v) => (
                    <li key={v.orderId} className="flex items-center justify-between gap-3 border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="font-mono text-xs font-semibold text-rose">{v.orderId}</p>
                        <p className="truncate text-sm text-ink">{v.service}</p>
                        <p className="text-xxs text-ink-faint">{v.area} · {v.deliverySlot}</p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <StatusBadge tone={deliveryStatusTone[v.status]} dot={false}>{v.status}</StatusBadge>
                        <StatusBadge tone={paymentStatusTone[v.paymentStatus] ?? "neutral"} dot={false}>{v.paymentStatus}</StatusBadge>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </DetailSectionCard>

            {issues.length > 0 && (
              <DetailSectionCard title="Open issues" icon={AlertTriangle}>
                <ul className="space-y-3">
                  {issues.map((i) => (
                    <li key={i.id} className="flex items-center justify-between gap-3 border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="truncate text-sm text-ink">{i.issueType}</p>
                        <p className="text-xxs text-ink-faint">{i.orderId} · {i.actionNeeded}</p>
                      </div>
                      <Chip tone={priorityTone[i.priority]}>{i.priority}</Chip>
                    </li>
                  ))}
                </ul>
              </DetailSectionCard>
            )}
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Driver" icon={UserRound}>
              <FieldGrid cols={2}>
                <Field label="Zone" value={<span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{d.zone}</span>} />
                <Field label="Assigned" value={d.assignedOrders} />
                <Field label="Done today" value={d.completedToday} />
                <Field label="Delayed" value={d.delayedJobs} />
                <Field label="Rating" value={<span className="inline-flex items-center gap-1"><Star className="h-3 w-3 text-warning" />{d.rating.toFixed(1)}</span>} />
                <Field label="PPI score" value={d.ppiScore} />
                <Field label="Last active" value={formatRelativeTime(d.lastActive)} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Driver view — customer area/city only. No customer name, phone, email or full address.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
