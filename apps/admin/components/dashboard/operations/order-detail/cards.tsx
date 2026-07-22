"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Info, MapPin, User, CreditCard, Building2, StickyNote, MessagesSquare,
  History, Eye, EyeOff, Send, ArrowRight, ShieldCheck, LifeBuoy,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { orderStatusTone, paymentTone, convStatusTone } from "@/lib/dashboard/status-maps";
import { qualityTone } from "@/lib/dashboard/operations-data";
import { formatCurrency, formatRelativeTime, maskPhone } from "@/lib/dashboard/formatters";
import type { Order } from "@/lib/dashboard/types";
import { SectionCard, Field, FieldGrid, Chip } from "./primitives";
import {
  customerType, customerStats, pendingAmount, qcStatus, deliverySlotLabel,
  relatedConversation, relatedIssues, orderEvents, seedNotes, isFlagged,
  type InternalNote,
} from "./data";

/* ------------------------------- Order overview ----------------------------- */

export function OrderOverviewCard({ order }: { order: Order }) {
  const conv = relatedConversation(order);
  const issues = relatedIssues(order);
  return (
    <SectionCard title="Order overview" icon={Info}>
      <FieldGrid cols={3}>
        <Field label="Order ID" value={order.id} mono />
        <Field label="Status" value={<StatusBadge tone={orderStatusTone[order.status]}>{order.status}</StatusBadge>} />
        <Field label="Source" value={order.channel} />
        <Field label="Service" value={order.service} />
        <Field label="Market" value={`${order.city}, ${order.market}`} />
        <Field label="Linked conversation" value={conv ? <span className="font-mono">{conv.id}</span> : "—"} />
      </FieldGrid>
      {(isFlagged(order) || issues.length > 0) && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {isFlagged(order) && <Chip tone="danger">Concern raised</Chip>}
          {issues.map((i) => <Chip key={i.id} tone="warning">{i.issueType}</Chip>)}
        </div>
      )}
      <p className="mt-4 text-xs text-ink-muted">Special instructions and internal reasoning are kept out of customer- and facility-facing views (privacy firewall).</p>
    </SectionCard>
  );
}

/* --------------------------- Pickup & delivery details ---------------------- */

export function PickupDeliveryCard({ order }: { order: Order }) {
  return (
    <SectionCard title="Pickup & delivery" icon={MapPin}>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-3">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-rose">Pickup</p>
          <Field label="Area / City" value={<span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{order.city}, {order.market}</span>} />
          <Field label="Slot" value={order.pickupSlot} />
          <Field label="Address" value={<span className="text-ink-muted">Full address is role-gated (authorized detail view).</span>} />
        </div>
        <div className="space-y-3 sm:border-l sm:border-border/60 sm:pl-5">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-rose">Delivery</p>
          <Field label="Area / City" value={<span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{order.city}, {order.market}</span>} />
          <Field label="Slot" value={deliverySlotLabel(order)} />
          <Field label="Contact" value={<span className="text-ink-muted">Reach the customer through the WhatsApp conversation only.</span>} />
        </div>
      </div>
    </SectionCard>
  );
}

/* ------------------------------ Customer snapshot --------------------------- */

export function CustomerSnapshotCard({ order }: { order: Order }) {
  const [reveal, setReveal] = useState(false);
  const { totalOrders, lastOrderDate } = customerStats(order);
  return (
    <SectionCard
      title="Customer"
      icon={User}
      action={
        <button type="button" onClick={() => setReveal((r) => !r)} className="inline-flex items-center gap-1.5 text-xxs font-semibold text-ink-muted transition-colors hover:text-ink">
          {reveal ? <><EyeOff className="h-3.5 w-3.5" /> Hide</> : <><Eye className="h-3.5 w-3.5" /> Reveal phone</>}
        </button>
      }
    >
      <FieldGrid>
        <Field label="Name" value={order.customer} />
        <Field label="Type" value={customerType(order)} />
        <Field label="Phone" value={reveal ? order.phone : maskPhone(order.phone)} mono />
        <Field label="City / Area" value={`${order.city}, ${order.market}`} />
        <Field label="Total orders" value={totalOrders} />
        <Field label="Last order" value={formatRelativeTime(lastOrderDate)} />
      </FieldGrid>
      {reveal && <p className="mt-3 text-xxs text-warning">Full number revealed — role-gated. This access is logged.</p>}
    </SectionCard>
  );
}

/* ------------------------------ Payment snapshot ---------------------------- */

export function PaymentSnapshotCard({ order }: { order: Order }) {
  const pending = pendingAmount(order);
  const refundRelevant = order.payment === "Refunded" || order.status === "Concern Raised";
  return (
    <SectionCard title="Payment" icon={CreditCard}>
      <FieldGrid>
        <Field label="Status" value={<StatusBadge tone={paymentTone[order.payment]}>{order.payment}</StatusBadge>} />
        <Field label="Method" value={order.channel === "B2B" ? "Invoice" : "Card / Pay on delivery"} />
        <Field label="Total amount" value={<span className="text-base font-semibold">{formatCurrency(order.amount)}</span>} />
        <Field label="Pending" value={pending > 0 ? formatCurrency(pending) : "None"} />
        {order.channel === "B2B" && <Field label="Invoice" value={order.payment === "Paid" ? "Settled" : "Sent — awaiting payment"} />}
        {refundRelevant && <Field label="Refund" value={order.payment === "Refunded" ? "Refund issued" : "Under review"} />}
      </FieldGrid>
      <p className="mt-3 text-xxs text-ink-faint">Refunds and adjustments require approval before they take effect.</p>
    </SectionCard>
  );
}

/* --------------------------- Facility / driver card ------------------------- */

export function AssignmentCard({ order }: { order: Order }) {
  const qc = qcStatus(order);
  const readyForHandoff = order.status === "Ready for Delivery";
  return (
    <SectionCard title="Assignment" icon={Building2}>
      <FieldGrid>
        <Field label="Facility" value={order.facility || "Unassigned"} />
        <Field label="Driver" value={order.driver ?? "Unassigned"} />
        <Field label="Assignment" value={order.driver ? "Driver assigned" : "Awaiting driver"} />
        <Field label="Quality check" value={<Chip tone={qualityTone[qc]}>{qc}</Chip>} />
      </FieldGrid>
      <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-border/70 bg-surface-2 px-3.5 py-2.5">
        <ShieldCheck className={cn("h-4 w-4 shrink-0", readyForHandoff ? "text-success" : "text-ink-faint")} />
        <p className="text-xs text-ink-muted">{readyForHandoff ? "Ready for handoff to delivery." : "Handoff opens once the order passes QC and is marked ready."}</p>
      </div>
    </SectionCard>
  );
}

/* ------------------------------ Internal notes ------------------------------ */

export function InternalNotesPanel({ order }: { order: Order }) {
  const [notes, setNotes] = useState<InternalNote[]>(() => seedNotes(order));
  const [draft, setDraft] = useState("");

  const add = () => {
    const body = draft.trim();
    if (!body) return;
    setNotes((n) => [{ id: `n-${n.length + 1}`, author: "You", at: order.createdAt, body }, ...n]);
    setDraft("");
  };

  return (
    <SectionCard title="Internal notes" icon={StickyNote}>
      <div className="space-y-2.5">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder="Add an internal note (not visible to the customer)…"
          className="w-full resize-none rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose/40 focus:outline-none"
        />
        <div className="flex justify-end">
          <Button variant="primary" size="sm" onClick={add} disabled={!draft.trim()}><Send className="h-3.5 w-3.5" /> Add note</Button>
        </div>
      </div>
      {notes.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="rounded-xl border border-border/70 bg-surface-2 px-3.5 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold text-ink">{n.author}</p>
                <p className="text-xxs text-ink-faint">{formatRelativeTime(n.at)}</p>
              </div>
              <p className="mt-1.5 text-sm text-ink-muted">{n.body}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-xs text-ink-faint">No internal notes yet.</p>
      )}
    </SectionCard>
  );
}

/* --------------------------- Related conversation --------------------------- */

export function RelatedConversationCard({ order }: { order: Order }) {
  const conv = relatedConversation(order);
  const issues = relatedIssues(order);
  const convHref = conv ? `/operations/customer-facing?conversationId=${conv.id}&orderId=${order.id}` : "/operations/customer-facing";
  return (
    <SectionCard title="Related conversation" icon={MessagesSquare}>
      {conv ? (
        <>
          <div className="rounded-xl border border-border/70 bg-surface-2 px-3.5 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold text-ink">{conv.customer}</p>
              <StatusBadge tone={convStatusTone[conv.status]}>{conv.status}</StatusBadge>
            </div>
            <p className="mt-2 line-clamp-2 text-sm text-ink-muted">“{conv.lastMessage}”</p>
            <p className="mt-1.5 text-xxs text-ink-faint">Updated {formatRelativeTime(conv.updatedAt)}</p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link href={convHref}><Button variant="primary" size="sm"><MessagesSquare className="h-3.5 w-3.5" /> Open conversation</Button></Link>
            <Link href={convHref}><Button variant="secondary" size="sm">View chat <ArrowRight className="h-3.5 w-3.5" /></Button></Link>
          </div>
        </>
      ) : (
        <p className="text-xs text-ink-faint">No WhatsApp conversation is linked to this order yet.</p>
      )}
      {issues.length > 0 && (
        <div className="mt-3 flex items-center gap-2 border-t border-border/60 pt-3">
          <LifeBuoy className="h-4 w-4 text-warning" />
          <span className="text-xs text-ink-muted">{issues.length} linked ticket{issues.length === 1 ? "" : "s"} / escalation{issues.length === 1 ? "" : "s"}</span>
        </div>
      )}
    </SectionCard>
  );
}

/* ------------------------------- Order events ------------------------------- */

export function OrderEventsFeed({ order }: { order: Order }) {
  const events = orderEvents(order);
  return (
    <SectionCard title="Order events" icon={History}>
      <ol className="space-y-3.5">
        {events.map((e) => (
          <li key={e.id} className="flex gap-3">
            <span className={cn(
              "mt-1.5 h-2 w-2 shrink-0 rounded-full",
              e.tone === "danger" ? "bg-danger" : e.tone === "warning" ? "bg-warning" : e.tone === "rose" ? "bg-rose" : "bg-info",
            )} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-sm font-medium text-ink">{e.label}</p>
                <p className="text-xxs text-ink-faint">{formatRelativeTime(e.at)}</p>
              </div>
              {e.detail && <p className="text-xs text-ink-muted">{e.detail}</p>}
              <p className="text-xxs text-ink-faint">{e.actor}</p>
            </div>
          </li>
        ))}
      </ol>
    </SectionCard>
  );
}
