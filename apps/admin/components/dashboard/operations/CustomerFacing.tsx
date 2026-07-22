"use client";

import { useMemo, useState } from "react";
import {
  MessagesSquare, MessageSquare, LifeBuoy, Ban, PhoneCall, AlertTriangle, Flame,
  Reply, Check, X, ArrowUpRight, StickyNote, Undo2, MapPin, Link2, SearchX, Hand,
} from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { WhatsAppInbox } from "@/components/dashboard/whatsapp/WhatsAppInbox";
import { orders, conversations, tickets } from "@/lib/dashboard/mock-data";
import {
  customerFacingKpis, cancellations, customerFollowups,
  type Cancellation, type Followup,
} from "@/lib/dashboard/operations-data";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterConversations, filterTickets, filterFollowups, filterByOrderRef, activeFilterCount } from "@/lib/dashboard/filters";
import { ticketStatusTone, convStatusTone, priorityTone } from "@/lib/dashboard/status-maps";
import type { Conversation, Ticket } from "@/lib/dashboard/types";
import {
  WorkflowTabs, CardGrid, RecordCard, DetailDrawer, DetailFields, DrawerSection,
  DrawerActions, Badge, maskPhone, type WorkflowTab, type DrawerAction,
} from "./workspace/Workspace";

/* ============================================================================
 * Customer Facing subsection. Top tabs are inbox/support WORKFLOW views for THIS
 * page only — never navigation to another Operations subsection (that lives in
 * the left sidebar). The WhatsApp Inbox tab keeps the full interactive inbox;
 * every other tab is a clickable card grid whose actions live inside the
 * DetailDrawer. See docs/architecture/operations-navigation.md.
 *
 * PRIVACY: phones are masked in lists; sensitive customer data stays hidden.
 * ========================================================================== */

type TabId =
  | "inbox" | "pending" | "takeover" | "tickets"
  | "cancellations" | "followups" | "complaints" | "escalations";

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "inbox", label: "WhatsApp Inbox" },
  { id: "pending", label: "Pending Replies" },
  { id: "takeover", label: "Human Takeover" },
  { id: "tickets", label: "Tickets" },
  { id: "cancellations", label: "Cancellations" },
  { id: "followups", label: "Follow-ups" },
  { id: "complaints", label: "Complaints" },
  { id: "escalations", label: "Escalations" },
];

/* Tickets that represent customer complaints vs escalated (urgent) items. */
const COMPLAINT_CATEGORIES = new Set<Ticket["category"]>(["Damage", "Quality", "Lost Item"]);
const isComplaint = (t: Ticket) => COMPLAINT_CATEGORIES.has(t.category);
const isEscalation = (t: Ticket) => t.priority === "Urgent" && t.status !== "Resolved";

/* -------------------------------- Detail bodies ----------------------------- */

function ConversationDetail({ c }: { c: Conversation }) {
  return (
    <>
      <DrawerSection title="Conversation">
        <DetailFields
          fields={[
            { label: "Customer", value: c.customer },
            { label: "Phone", value: maskPhone(c.phone) },
            { label: "City", value: c.city },
            { label: "Status", value: <Badge tone={convStatusTone[c.status]}>{c.status}</Badge> },
            { label: "Mode", value: <Badge tone={c.mode === "AI" ? "info" : "rose"}>{c.mode}</Badge> },
            { label: "Linked order", value: c.assignedOrder ? <span className="font-mono">{c.assignedOrder}</span> : "—" },
            { label: "Unread", value: c.unread },
            { label: "Updated", value: formatRelativeTime(c.updatedAt) },
          ]}
        />
      </DrawerSection>
      <DrawerSection title="Last message">
        <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-ink">{c.lastMessage}</p>
      </DrawerSection>
      <DrawerSection title="Suggested action">
        <p className="text-sm text-ink-muted">{c.suggestedAction}</p>
      </DrawerSection>
      <DrawerSection title="Privacy">
        <p className="text-xs text-ink-muted">Phone is masked. The full number and address are visible only in the secure detail view for authorized roles.</p>
      </DrawerSection>
    </>
  );
}

function TicketDetail({ t }: { t: Ticket }) {
  return (
    <DrawerSection title="Ticket">
      <DetailFields
        fields={[
          { label: "Reference", value: <span className="font-mono">{t.id}</span> },
          { label: "Subject", value: t.subject },
          { label: "Category", value: t.category },
          { label: "Priority", value: <Badge tone={priorityTone[t.priority]}>{t.priority}</Badge> },
          { label: "Source", value: t.source },
          { label: "Status", value: <Badge tone={ticketStatusTone[t.status]}>{t.status}</Badge> },
          { label: "Assignee", value: t.assignee },
          { label: "SLA left", value: t.status === "Resolved" ? "—" : `${t.slaMinutesLeft}m` },
          { label: "City", value: t.city },
          { label: "Created", value: formatRelativeTime(t.createdAt) },
        ]}
      />
    </DrawerSection>
  );
}

function CancellationDetail({ c }: { c: Cancellation }) {
  return (
    <DrawerSection title="Cancellation request">
      <DetailFields
        fields={[
          { label: "Reference", value: <span className="font-mono">{c.id}</span> },
          { label: "Order", value: <span className="font-mono">{c.orderId}</span> },
          { label: "Customer", value: c.customer },
          { label: "Phone", value: maskPhone(c.phone) },
          { label: "Reason", value: c.reason },
          { label: "Refund", value: c.refund > 0 ? formatCurrency(c.refund) : "None" },
          { label: "Status", value: <Badge tone={c.status === "Approved" ? "success" : c.status === "Declined" ? "danger" : "warning"}>{c.status}</Badge> },
          { label: "Requested", value: formatRelativeTime(c.requestedAt) },
        ]}
      />
      <p className="mt-3 text-xs text-ink-muted">Cancellations outside policy and any refund require human approval before they take effect.</p>
    </DrawerSection>
  );
}

function FollowupDetail({ f }: { f: Followup }) {
  return (
    <DrawerSection title="Customer follow-up">
      <DetailFields
        fields={[
          { label: "Reference", value: <span className="font-mono">{f.id}</span> },
          { label: "Customer", value: f.customer },
          { label: "City", value: f.city },
          { label: "Reason", value: f.reason },
          { label: "Channel", value: f.channel },
          { label: "Due", value: formatRelativeTime(f.due) },
          { label: "Status", value: <Badge tone={f.status === "Due" ? "warning" : f.status === "Done" ? "success" : "info"}>{f.status}</Badge> },
        ]}
      />
    </DrawerSection>
  );
}

/* -------------------------------- Actions ----------------------------------- */

const CONVERSATION_ACTIONS = (c: Conversation): DrawerAction[] => [
  { label: "Send reply", icon: Reply, tone: "primary", approval: true },
  { label: c.mode === "Human" ? "Return to AI" : "Human takeover", icon: Hand },
  { label: "Open chat", icon: MessageSquare },
  { label: "View linked order", icon: Link2, disabled: !c.assignedOrder },
  { label: "Escalate to human", icon: ArrowUpRight },
  { label: "Add note", icon: StickyNote },
];

const TICKET_ACTIONS = (t: Ticket): DrawerAction[] => [
  { label: "Respond", icon: Reply, tone: "primary" },
  { label: "Reassign", icon: MessagesSquare },
  { label: "Escalate to human", icon: ArrowUpRight },
  { label: "View linked order", icon: Link2 },
  { label: "Add note", icon: StickyNote },
  { label: "Resolve ticket", icon: Check, disabled: t.status === "Resolved" },
];

const CANCELLATION_ACTIONS = (): DrawerAction[] => [
  { label: "Approve cancellation", icon: Check, tone: "primary", approval: true },
  { label: "Keep order", icon: X },
  { label: "Refund request", icon: Undo2, approval: true },
  { label: "Open chat", icon: MessageSquare },
  { label: "Add note", icon: StickyNote },
];

const FOLLOWUP_ACTIONS = (f: Followup): DrawerAction[] => [
  { label: f.channel === "Email" ? "Send email" : "Send message", icon: MessageSquare, tone: "primary" },
  { label: "Reschedule", icon: PhoneCall },
  { label: "Mark done", icon: Check, disabled: f.status === "Done" },
  { label: "Add note", icon: StickyNote },
];

const ACTION_NOTE = "Cancellations, refunds and outbound replies require approval before they take effect. Nothing is sent live from this view.";

/* --------------------------------- Section ---------------------------------- */

type Selected =
  | { kind: "conversation"; data: Conversation }
  | { kind: "ticket"; data: Ticket }
  | { kind: "cancellation"; data: Cancellation }
  | { kind: "followup"; data: Followup }
  | null;

export function CustomerFacing() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<TabId>("inbox");
  const [selected, setSelected] = useState<Selected>(null);

  const orderIndex = useMemo(() => new Map(orders.map((o) => [o.id, o])), []);
  const fConversations = useMemo(() => filterConversations(conversations, filters), [filters]);
  const fTickets = useMemo(() => filterTickets(tickets, filters), [filters]);
  const fCancellations = useMemo(() => filterByOrderRef(cancellations, filters, orderIndex), [filters, orderIndex]);
  const fFollowups = useMemo(() => filterFollowups(customerFollowups, filters), [filters]);
  const isFiltered = activeFilterCount(filters) > 0;

  const pending = fConversations.filter((c) => c.status === "Awaiting reply");
  const takeover = fConversations.filter((c) => c.status === "Human takeover");
  const complaints = fTickets.filter(isComplaint);
  const escalations = fTickets.filter(isEscalation);

  const count: Record<TabId, number> = {
    inbox: fConversations.length,
    pending: pending.length,
    takeover: takeover.length,
    tickets: fTickets.length,
    cancellations: fCancellations.length,
    followups: fFollowups.length,
    complaints: complaints.length,
    escalations: escalations.length,
  };

  const tabs: WorkflowTab[] = TAB_LABELS.map((t) => ({ id: t.id, label: t.label, count: count[t.id] }));

  const convCard = (c: Conversation) => (
    <RecordCard
      key={c.id}
      title={c.customer}
      onClick={() => setSelected({ kind: "conversation", data: c })}
      badges={<><Badge tone={convStatusTone[c.status]}>{c.status}</Badge><Badge tone={c.mode === "AI" ? "info" : "rose"}>{c.mode}</Badge></>}
      fields={[
        { label: "City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{c.city}</span> },
        { label: "Order", value: c.assignedOrder ? <span className="font-mono">{c.assignedOrder}</span> : "—" },
        { label: "Phone", value: maskPhone(c.phone) },
        { label: "Updated", value: formatRelativeTime(c.updatedAt) },
      ]}
      footer={<span className="flex items-center justify-between"><span className="line-clamp-1">{c.lastMessage}</span>{c.unread > 0 && <span className="ml-2 shrink-0 rounded-full bg-rose/12 px-1.5 text-xxs font-semibold text-rose">{c.unread}</span>}</span>}
    />
  );

  const ticketCard = (t: Ticket) => (
    <RecordCard
      key={t.id}
      id={t.id}
      title={t.subject}
      onClick={() => setSelected({ kind: "ticket", data: t })}
      badges={<><Badge tone={priorityTone[t.priority]}>{t.priority}</Badge><Badge tone={ticketStatusTone[t.status]}>{t.status}</Badge></>}
      fields={[
        { label: "Category", value: t.category },
        { label: "Assignee", value: t.assignee },
        { label: "City", value: t.city },
        { label: "SLA", value: t.status === "Resolved" ? "—" : `${t.slaMinutesLeft}m` },
      ]}
    />
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Customer support snapshot · phones masked</p>
        <SnapshotBadge active={isFiltered} />
      </div>
      <StatGrid stats={customerFacingKpis} cols="4" />
      <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 px-3.5 py-2.5">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs text-ink-muted"><span className="font-semibold text-ink">Privacy firewall on.</span> Phones are masked in lists; full number and address stay hidden unless the role is authorized.</p>
      </div>
      <div className="rounded-xl border border-border bg-surface px-3 py-2.5 shadow-card">
        <FilterBar />
      </div>

      <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />

      {tab === "inbox" ? (
        <section className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h3 className="font-display text-[0.95rem] font-semibold text-ink">WhatsApp Agent</h3>
              <p className="mt-0.5 text-xs text-ink-muted">Live customer conversations. The agent handles the happy path; human takeover appears when it raises a flag.</p>
            </div>
            <Badge tone="success">Operational</Badge>
          </div>
          <WhatsAppInbox />
        </section>
      ) : tab === "pending" ? (
        pending.length === 0 ? <EmptyState icon={Reply} title="No pending replies" description="Conversations waiting on a customer reply appear here." /> : <CardGrid>{pending.map(convCard)}</CardGrid>
      ) : tab === "takeover" ? (
        takeover.length === 0 ? <EmptyState icon={Hand} title="No human takeovers" description="Conversations an operator has taken over appear here." /> : <CardGrid>{takeover.map(convCard)}</CardGrid>
      ) : tab === "tickets" ? (
        fTickets.length === 0 ? <EmptyState icon={LifeBuoy} title="No tickets" description="Support tickets and concerns appear here." /> : <CardGrid>{fTickets.map(ticketCard)}</CardGrid>
      ) : tab === "complaints" ? (
        complaints.length === 0 ? <EmptyState icon={SearchX} title="No complaints" description="Damage, quality and lost-item complaints appear here." /> : <CardGrid>{complaints.map(ticketCard)}</CardGrid>
      ) : tab === "escalations" ? (
        escalations.length === 0 ? <EmptyState icon={Flame} title="No escalations" description="Urgent tickets escalated for a human appear here." /> : <CardGrid>{escalations.map(ticketCard)}</CardGrid>
      ) : tab === "cancellations" ? (
        fCancellations.length === 0 ? <EmptyState icon={Ban} title="No cancellations" description="Cancellation requests awaiting a decision appear here." /> : (
          <CardGrid>
            {fCancellations.map((c) => (
              <RecordCard
                key={c.id}
                id={c.id}
                title={c.customer}
                onClick={() => setSelected({ kind: "cancellation", data: c })}
                badges={<Badge tone={c.status === "Approved" ? "success" : c.status === "Declined" ? "danger" : "warning"}>{c.status}</Badge>}
                fields={[
                  { label: "Order", value: <span className="font-mono">{c.orderId}</span> },
                  { label: "Refund", value: c.refund > 0 ? formatCurrency(c.refund) : "None" },
                  { label: "Phone", value: maskPhone(c.phone) },
                  { label: "Requested", value: formatRelativeTime(c.requestedAt) },
                ]}
                footer={c.reason}
              />
            ))}
          </CardGrid>
        )
      ) : (
        fFollowups.length === 0 ? <EmptyState icon={PhoneCall} title="No follow-ups" description="Scheduled and due customer check-ins appear here." /> : (
          <CardGrid>
            {fFollowups.map((f) => (
              <RecordCard
                key={f.id}
                id={f.id}
                title={f.customer}
                onClick={() => setSelected({ kind: "followup", data: f })}
                badges={<Badge tone={f.status === "Due" ? "warning" : f.status === "Done" ? "success" : "info"}>{f.status}</Badge>}
                fields={[
                  { label: "City", value: f.city },
                  { label: "Channel", value: f.channel },
                  { label: "Due", value: formatRelativeTime(f.due) },
                ]}
                footer={f.reason}
              />
            ))}
          </CardGrid>
        )
      )}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        eyebrow={
          selected?.kind === "ticket" ? "Ticket"
          : selected?.kind === "cancellation" ? "Cancellation"
          : selected?.kind === "followup" ? "Follow-up"
          : "Conversation"
        }
        title={
          selected?.kind === "ticket" ? selected.data.id
          : selected?.kind === "cancellation" ? selected.data.id
          : selected?.kind === "followup" ? selected.data.customer
          : selected?.kind === "conversation" ? selected.data.customer
          : ""
        }
        subtitle={
          selected?.kind === "ticket" ? selected.data.subject
          : selected?.kind === "cancellation" ? selected.data.orderId
          : undefined
        }
        actions={
          selected && (
            <DrawerActions
              actions={
                selected.kind === "conversation" ? CONVERSATION_ACTIONS(selected.data)
                : selected.kind === "ticket" ? TICKET_ACTIONS(selected.data)
                : selected.kind === "cancellation" ? CANCELLATION_ACTIONS()
                : FOLLOWUP_ACTIONS(selected.data)
              }
              note={ACTION_NOTE}
            />
          )
        }
      >
        {selected?.kind === "conversation" && <ConversationDetail c={selected.data} />}
        {selected?.kind === "ticket" && <TicketDetail t={selected.data} />}
        {selected?.kind === "cancellation" && <CancellationDetail c={selected.data} />}
        {selected?.kind === "followup" && <FollowupDetail f={selected.data} />}
      </DetailDrawer>
    </div>
  );
}
