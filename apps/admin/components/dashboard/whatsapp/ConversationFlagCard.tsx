"use client";

import { AlertTriangle, Users, Lightbulb, MessageSquareQuote, Package } from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { orderStatusTone, paymentTone } from "@/lib/dashboard/status-maps";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import { priorityTone, type InboxFlag, type InboxOrder } from "@/lib/dashboard/whatsapp-inbox";

/**
 * Handoff / escalation card — shows why the agent raised a hand and what the
 * operator should do next. Rendered inside the conversation context panel.
 */
export function ConversationFlagCard({ flag }: { flag: InboxFlag }) {
  return (
    <div className="rounded-xl border border-warning/25 bg-warning/[0.06] p-3.5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <p className="text-xs font-semibold text-ink">Human intervention required</p>
        <StatusBadge tone={priorityTone[flag.priority]} dot={false} className="ml-auto uppercase">
          {flag.priority}
        </StatusBadge>
      </div>

      <dl className="mt-3 space-y-2 text-xs">
        <div className="flex items-start justify-between gap-3">
          <dt className="text-ink-muted">Reason</dt>
          <dd className="text-right font-medium text-ink">{flag.reason}</dd>
        </div>
        <div className="flex items-start justify-between gap-3">
          <dt className="flex items-center gap-1 text-ink-muted">
            <Users className="h-3 w-3" /> Team
          </dt>
          <dd className="text-right font-medium text-ink">{flag.team}</dd>
        </div>
      </dl>

      {flag.suggestedReply && (
        <div className="mt-3 rounded-lg border border-border bg-surface p-2.5">
          <p className="flex items-center gap-1 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
            <MessageSquareQuote className="h-3 w-3" /> Suggested reply
          </p>
          <p className="mt-1 text-xs italic text-ink-muted">“{flag.suggestedReply}”</p>
        </div>
      )}

      {flag.suggestedAction && (
        <div className="mt-2 flex items-start gap-1.5 rounded-lg bg-surface px-2.5 py-2">
          <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-rose" />
          <p className="text-xs text-ink-muted">{flag.suggestedAction}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Compact, privacy-safe order summary. No full address, no phone, no card data —
 * area + city only.
 */
export function OrderContextCard({ order }: { order: InboxOrder }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3.5">
      <div className="flex items-center gap-2">
        <Package className="h-4 w-4 text-ink-faint" />
        <span className="font-mono text-xs font-semibold text-ink">{order.id}</span>
        <StatusBadge tone={orderStatusTone[order.status] ?? "neutral"} dot={false} className="ml-auto">
          {order.status}
        </StatusBadge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        <Field label="Service" value={order.service} />
        <Field
          label="Payment"
          value={<StatusBadge tone={paymentTone[order.payment] ?? "neutral"} dot={false}>{order.payment}</StatusBadge>}
        />
        <Field label="Area / City" value={`${order.area}, ${order.city}`} />
        <Field label="Pickup slot" value={order.pickupSlot} />
        <Field label="Last update" value={formatRelativeTime(order.lastUpdate)} />
      </dl>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className="mt-0.5 font-medium text-ink">{value}</dd>
    </div>
  );
}
