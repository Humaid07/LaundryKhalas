"use client";

import { useMemo } from "react";
import {
  MessagesSquare,
  LifeBuoy,
  Pencil,
  Ban,
  PhoneCall,
  Check,
  X,
  MessageSquare,
  MapPin,
  Clock,
  SearchX,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { Tabs, type TabDef } from "@/components/dashboard/ui/Tabs";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState } from "@/components/dashboard/ui/states";
import { ActivityTimeline } from "@/components/dashboard/widgets";
import { WhatsAppInbox } from "@/components/dashboard/whatsapp/WhatsAppInbox";
import { orders, conversations, tickets } from "@/lib/dashboard/mock-data";
import {
  customerFacingKpis,
  cancellations,
  orderChanges,
  customerFollowups,
  customerActivity,
  type Cancellation,
  type OrderChange,
  type Followup,
} from "@/lib/dashboard/operations-data";
import { formatCurrency, formatRelativeTime, maskPhone } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterConversations, filterTickets, filterFollowups, filterByOrderRef } from "@/lib/dashboard/filters";
import {
  ticketStatusTone,
  convStatusTone,
  priorityTone,
  riskTone,
} from "@/lib/dashboard/status-maps";
import type { Conversation, Ticket } from "@/lib/dashboard/types";

const noMatch = <EmptyState icon={SearchX} title="No matches" description="No records match the active filters." />;

/* --------------------------------- tables ---------------------------------- */

// Privacy: no phone column — phones are masked; support context stays minimal.
const conversationCols: Column<Conversation>[] = [
  { key: "customer", header: "Customer", primary: true, cell: (c) => <span className="whitespace-nowrap font-medium text-ink">{c.customer}</span> },
  { key: "city", header: "City", cell: (c) => <span className="flex items-center gap-1 whitespace-nowrap text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{c.city}</span> },
  { key: "last", header: "Last Message", cell: (c) => <span className="line-clamp-1 max-w-[16rem] text-xs text-ink-muted">{c.lastMessage}</span> },
  { key: "status", header: "Status", cell: (c) => <StatusBadge tone={convStatusTone[c.status]}>{c.status}</StatusBadge> },
  { key: "mode", header: "Mode", cell: (c) => <StatusBadge tone={c.mode === "AI" ? "info" : "rose"} dot={false}>{c.mode}</StatusBadge> },
  { key: "order", header: "Order", cell: (c) => (c.assignedOrder ? <span className="font-mono text-xs text-ink-muted">{c.assignedOrder}</span> : <span className="text-xs text-ink-faint">—</span>) },
  { key: "suggested", header: "Suggested Action", cell: (c) => <span className="text-xs text-ink-faint">{c.suggestedAction}</span> },
  { key: "updated", header: "Updated", cell: (c) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(c.updatedAt)}</span> },
  {
    key: "actions",
    header: "",
    align: "right",
    cell: (c) => (
      <div className="flex justify-end gap-1">
        {c.unread > 0 && <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-rose/12 px-1.5 text-xxs font-semibold text-rose tnum">{c.unread}</span>}
        <Button size="sm" variant="ghost" aria-label="Open conversation"><MessageSquare className="h-3.5 w-3.5" /></Button>
        <Button size="sm" variant="secondary">Open</Button>
      </div>
    ),
  },
];

const ticketCols: Column<Ticket>[] = [
  { key: "id", header: "Ticket", primary: true, cell: (t) => <span className="font-mono text-xs font-semibold text-ink">{t.id}</span> },
  { key: "subject", header: "Subject", cell: (t) => <span className="text-ink">{t.subject}</span> },
  { key: "category", header: "Category", cell: (t) => <StatusBadge tone="neutral" dot={false}>{t.category}</StatusBadge> },
  { key: "priority", header: "Priority", cell: (t) => <StatusBadge tone={priorityTone[t.priority]}>{t.priority}</StatusBadge> },
  { key: "status", header: "Status", cell: (t) => <StatusBadge tone={ticketStatusTone[t.status]}>{t.status}</StatusBadge> },
  { key: "assignee", header: "Assignee", cell: (t) => <span className="whitespace-nowrap text-ink-muted">{t.assignee}</span> },
  {
    key: "sla",
    header: "SLA",
    cell: (t) =>
      t.status === "Resolved" ? <span className="text-xs text-ink-faint">—</span> : (
        <span className={`font-mono text-xs tnum ${t.slaMinutesLeft < 30 ? "text-danger" : "text-ink-muted"}`}>{t.slaMinutesLeft}m</span>
      ),
  },
  { key: "action", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Respond</Button> },
];

function ConversationsTab({ rows }: { rows: Conversation[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader
        title="Customer conversations"
        subtitle={`${rows.length} of ${conversations.length} · WhatsApp — phones masked`}
        className="p-4"
        action={<StatusBadge tone="warning">{rows.filter((c) => c.status === "Awaiting reply").length} awaiting reply</StatusBadge>}
      />
      <div className="px-4 pb-4">
        <DataTable columns={conversationCols} rows={rows} rowKey={(c) => c.id} empty={noMatch} onRowLabel={(c) => <StatusBadge tone={convStatusTone[c.status]}>{c.status}</StatusBadge>} />
      </div>
    </Panel>
  );
}

function TicketsTab({ rows }: { rows: Ticket[] }) {
  return (
    <Panel padded={false}>
      <PanelHeader title="Tickets & concerns" subtitle={`${rows.filter((t) => t.status !== "Resolved").length} open · SLA tracked`} className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={ticketCols} rows={rows} rowKey={(t) => t.id} empty={noMatch} onRowLabel={(t) => <StatusBadge tone={priorityTone[t.priority]}>{t.priority}</StatusBadge>} />
      </div>
    </Panel>
  );
}

function ChangesTab({ rows }: { rows: OrderChange[] }) {
  return (
    <Panel>
      <PanelHeader title="Order change requests" subtitle="Every change is logged and needs approval" />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((c) => (
          <li key={c.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Pencil className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div>
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{c.orderId}</span> · {c.customer}</p>
                <p className="text-xs text-ink-muted">{c.change}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 sm:pl-0">
              <StatusBadge tone={riskTone[c.risk]} dot={false}>{c.risk} risk</StatusBadge>
              {c.status === "Applied" ? (
                <StatusBadge tone="success">Applied</StatusBadge>
              ) : (
                <>
                  <Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button>
                  <Button size="sm" variant="danger"><X className="h-3.5 w-3.5" /> Reject</Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function CancellationsTab({ rows }: { rows: Cancellation[] }) {
  return (
    <Panel>
      <PanelHeader title="Cancellation requests" subtitle="Cancellations outside policy need human approval" action={<StatusBadge tone="danger">{rows.filter((c) => c.status === "Awaiting Approval").length} pending</StatusBadge>} />
      {rows.length === 0 && noMatch}
      <ul className="space-y-2.5">
        {rows.map((c) => (
          <li key={c.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Ban className="mt-0.5 h-4 w-4 text-danger" />
              <div>
                <p className="text-sm text-ink"><span className="font-mono text-xs font-semibold">{c.orderId}</span> · {c.customer}</p>
                <p className="text-xs text-ink-muted">{c.reason} · refund {formatCurrency(c.refund)}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-7 sm:pl-0">
              <Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button>
              <Button size="sm" variant="secondary">Keep order</Button>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function FollowupsTab({ rows }: { rows: Followup[] }) {
  return (
    <Panel>
      <PanelHeader title="Customer follow-ups" subtitle="Scheduled and due check-ins" />
      {rows.length === 0 && noMatch}
      <ul className="divide-y divide-border">
        {rows.map((f) => (
          <li key={f.id} className="flex items-center justify-between gap-3 py-3">
            <div className="flex items-start gap-3">
              <PhoneCall className="mt-0.5 h-4 w-4 text-ink-faint" />
              <div>
                <p className="text-sm font-medium text-ink">{f.customer} <span className="text-xxs font-normal text-ink-faint">· {f.city}</span></p>
                <p className="text-xs text-ink-muted">{f.reason}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge tone={f.status === "Due" ? "warning" : f.status === "Done" ? "success" : "info"}>{f.status}</StatusBadge>
              {f.status !== "Done" && <Button size="sm" variant="secondary">{f.channel === "Email" ? "Email" : "Message"}</Button>}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function CustomerFacing() {
  const { filters } = useFilters();
  const orderIndex = useMemo(() => new Map(orders.map((o) => [o.id, o])), []);
  const fConversations = filterConversations(conversations, filters);
  const fTickets = filterTickets(tickets, filters);
  const fChanges = filterByOrderRef(orderChanges, filters, orderIndex);
  const fCancellations = filterByOrderRef(cancellations, filters, orderIndex);
  const fFollowups = filterFollowups(customerFollowups, filters);

  const tabs: TabDef[] = [
    { id: "conversations", label: "Conversations", icon: <MessagesSquare className="h-4 w-4" />, badge: fConversations.filter((c) => c.status === "Awaiting reply").length, content: <ConversationsTab rows={fConversations} /> },
    { id: "tickets", label: "Tickets / Concerns", icon: <LifeBuoy className="h-4 w-4" />, badge: fTickets.filter((t) => t.status !== "Resolved").length, content: <TicketsTab rows={fTickets} /> },
    { id: "cancel", label: "Cancellations", icon: <Ban className="h-4 w-4" />, badge: fCancellations.length, content: <CancellationsTab rows={fCancellations} /> },
    { id: "changes", label: "Order Changes", icon: <Pencil className="h-4 w-4" />, badge: fChanges.length, content: <ChangesTab rows={fChanges} /> },
    { id: "followups", label: "Follow-ups", icon: <PhoneCall className="h-4 w-4" />, content: <FollowupsTab rows={fFollowups} /> },
  ];

  return (
    <div className="space-y-5">
      <StatGrid stats={customerFacingKpis} cols="4" />

      {/* WhatsApp Agent inbox — the flagship customer-facing surface. Full width. */}
      <section className="space-y-3">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h3 className="font-display text-[0.95rem] font-semibold text-ink">WhatsApp Agent</h3>
            <p className="mt-0.5 text-xs text-ink-muted">
              Live customer conversations. The agent handles the happy path; human takeover appears when it raises a flag.
            </p>
          </div>
          <StatusBadge tone="success" className="hidden sm:inline-flex">Operational</StatusBadge>
        </div>
        <WhatsAppInbox />
      </section>

      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <Tabs tabs={tabs} />
        </div>
        <aside className="space-y-4">
          <Panel>
            <PanelHeader title="Customer activity" subtitle="Latest customer-side events" />
            <ActivityTimeline events={customerActivity} />
          </Panel>
          <Panel>
            <PanelHeader title="Customer actions" />
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Track Order", icon: MapPin },
                { label: "Respond to Ticket", icon: LifeBuoy },
                { label: "Change Details", icon: Pencil },
                { label: "Cancel Order", icon: Ban },
                { label: "Human Takeover", icon: PhoneCall },
                { label: "Contact Customer", icon: Clock },
              ].map((a) => (
                <button key={a.label} type="button" className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-2.5 py-2 text-left text-xs font-medium text-ink transition-colors hover:border-rose/40">
                  <a.icon className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                  <span className="truncate">{a.label}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-xxs text-ink-faint">Phones are masked (e.g. {maskPhone("+971 50 220 4471")}); sensitive info stays hidden.</p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
