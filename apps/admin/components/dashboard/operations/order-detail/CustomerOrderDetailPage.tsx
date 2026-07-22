"use client";

import {
  ListChecks, GitBranch, Gauge, Zap, RefreshCw, Truck, Building2,
  CalendarClock, StickyNote, MessageSquare, ArrowUpRight,
} from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import type { Order } from "@/lib/dashboard/types";
import { OrderHeader } from "./OrderHeader";
import { OrderSummaryStrip } from "./OrderSummaryStrip";
import { OrderLifecycleTimeline } from "./OrderLifecycleTimeline";
import { OrderItemsTable } from "./OrderItemsTable";
import {
  OrderOverviewCard, PickupDeliveryCard, CustomerSnapshotCard, PaymentSnapshotCard,
  AssignmentCard, InternalNotesPanel, RelatedConversationCard, OrderEventsFeed,
} from "./cards";
import { SectionCard } from "./primitives";
import { sla, nextStep } from "./data";

/* ------------------------------- sidebar cards ------------------------------ */

function SlaCard({ order }: { order: Order }) {
  const s = sla(order);
  return (
    <SectionCard title="SLA & next step" icon={Gauge}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-ink-muted">Delivery SLA</span>
        <StatusBadge tone={s.tone}>{s.label}</StatusBadge>
      </div>
      <div className="mt-3 rounded-xl border border-border/70 bg-surface-2 px-3.5 py-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Next step</p>
        <p className="mt-1 text-sm text-ink">{nextStep(order)}</p>
      </div>
    </SectionCard>
  );
}

function QuickActionsCard() {
  const actions = [
    { label: "Change status", icon: RefreshCw, primary: true },
    { label: "Assign driver", icon: Truck },
    { label: "Assign facility", icon: Building2 },
    { label: "Reschedule pickup", icon: CalendarClock },
    { label: "Add internal note", icon: StickyNote },
    { label: "Open customer chat", icon: MessageSquare },
    { label: "Escalate to human", icon: ArrowUpRight },
  ];
  return (
    <SectionCard title="Quick actions" icon={Zap}>
      <div className="grid gap-2">
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            className={
              a.primary
                ? "flex items-center gap-2.5 rounded-lg border border-rose/30 bg-rose/10 px-3 py-2 text-left text-sm font-medium text-rose transition-colors hover:bg-rose/16"
                : "flex items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-2 text-left text-sm font-medium text-ink transition-colors hover:border-rose/40"
            }
          >
            <a.icon className="h-4 w-4 shrink-0 opacity-80" />
            {a.label}
          </button>
        ))}
      </div>
      <p className="mt-3 text-xxs text-ink-faint">Cancellations and refunds are in the header’s “More actions” menu and require approval. Nothing is sent live from this view.</p>
    </SectionCard>
  );
}

/* --------------------------------- page ------------------------------------- */

export function CustomerOrderDetailPage({ order, backHref }: { order: Order; backHref: string }) {
  return (
    <div className="lk-enter space-y-6">
      <OrderHeader order={order} backHref={backHref} />
      <OrderSummaryStrip order={order} />

      <div className="grid gap-5 lg:grid-cols-3">
        {/* main column */}
        <div className="space-y-5 lg:col-span-2">
          <OrderOverviewCard order={order} />
          <SectionCard title="Items & service breakdown" icon={ListChecks}>
            <OrderItemsTable order={order} />
          </SectionCard>
          <PickupDeliveryCard order={order} />
          <SectionCard title="Order lifecycle" icon={GitBranch}>
            <OrderLifecycleTimeline order={order} />
          </SectionCard>
          <InternalNotesPanel order={order} />
          <RelatedConversationCard order={order} />
          <OrderEventsFeed order={order} />
        </div>

        {/* sidebar column */}
        <div className="space-y-5">
          <div className="space-y-5 lg:sticky lg:top-6">
            <CustomerSnapshotCard order={order} />
            <PaymentSnapshotCard order={order} />
            <AssignmentCard order={order} />
            <SlaCard order={order} />
            <QuickActionsCard />
          </div>
        </div>
      </div>
    </div>
  );
}
