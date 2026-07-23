"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  LifeBuoy, Ban, PhoneCall, Flame, Reply, MapPin, SearchX, Hand,
} from "lucide-react";
import { FilterBar } from "@/components/dashboard/shell/FilterBar";
import { WhatsAppInbox } from "@/components/dashboard/whatsapp/WhatsAppInbox";
import { orders, conversations, tickets } from "@/lib/dashboard/mock-data";
import { customerFollowups, cancellations } from "@/lib/dashboard/operations-data";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterConversations, filterTickets, filterFollowups, filterByOrderRef, activeFilterCount } from "@/lib/dashboard/filters";
import { ticketStatusTone, convStatusTone, priorityTone } from "@/lib/dashboard/status-maps";
import type { Conversation, Ticket } from "@/lib/dashboard/types";
import { maskPhone } from "./workspace/Workspace";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, EmptyState, StatusBadge,
  SnapshotBadge, type MinimalKpi, type WorkflowTab,
} from "@/components/dashboard/minimal";

/* Customer Facing subsection. Top tabs are inbox/support WORKFLOW views for THIS
 * page only. The WhatsApp Inbox tab IS the full conversation workspace; queue
 * previews open it, tickets open a full ticket detail page, cancellations open
 * their order. No drawers. PRIVACY: phones masked in lists. */

type TabId =
  | "inbox" | "pending" | "takeover" | "tickets"
  | "cancellations" | "followups" | "complaints" | "escalations";

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "inbox", label: "Inbox" },
  { id: "pending", label: "Pending" },
  { id: "takeover", label: "Takeover" },
  { id: "tickets", label: "Tickets" },
  { id: "cancellations", label: "Cancellations" },
  { id: "followups", label: "Follow-ups" },
  { id: "complaints", label: "Complaints" },
  { id: "escalations", label: "Escalations" },
];

const COMPLAINT_CATEGORIES = new Set<Ticket["category"]>(["Damage", "Quality", "Lost Item"]);
const isComplaint = (t: Ticket) => COMPLAINT_CATEGORIES.has(t.category);
const isEscalation = (t: Ticket) => t.priority === "Urgent" && t.status !== "Resolved";
const isTabId = (v: string | null): v is TabId => !!v && TAB_LABELS.some((t) => t.id === v);

export function CustomerFacing() {
  const router = useRouter();
  const search = useSearchParams();
  const { filters } = useFilters();
  const initial = search.get("tab");
  const [tab, setTab] = useState<TabId>(isTabId(initial) ? initial : "inbox");

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

  const kpis: MinimalKpi[] = [
    { label: "Open conversations", value: String(fConversations.length) },
    { label: "Pending replies", value: String(pending.length), tone: "warning" },
    { label: "Human takeover", value: String(takeover.length), tone: "rose" },
    { label: "Escalations", value: String(escalations.length), tone: "danger" },
  ];

  const convCard = (c: Conversation) => (
    <CompactRecordCard
      key={c.id}
      title={c.customer}
      status={{ label: c.status, tone: convStatusTone[c.status] }}
      fields={[
        { label: "City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{c.city}</span> },
        { label: "Order", value: c.assignedOrder ? <span className="font-mono">{c.assignedOrder}</span> : "—" },
        { label: "Phone", value: maskPhone(c.phone) },
      ]}
      meta={<StatusBadge tone={c.mode === "AI" ? "info" : "rose"} dot={false}>{c.mode}</StatusBadge>}
      onClick={() => setTab("inbox")}
    />
  );

  const ticketCard = (t: Ticket) => (
    <CompactRecordCard
      key={t.id}
      id={t.id}
      title={t.subject}
      status={{ label: t.priority, tone: priorityTone[t.priority] }}
      fields={[
        { label: "Category", value: t.category },
        { label: "Assignee", value: t.assignee },
        { label: "SLA", value: t.status === "Resolved" ? "—" : `${t.slaMinutesLeft}m` },
      ]}
      meta={<StatusBadge tone={ticketStatusTone[t.status]} dot={false}>{t.status}</StatusBadge>}
      href={`/operations/customer-facing/tickets/${t.id}?tab=${tab}`}
    />
  );

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />

      <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-xxs leading-relaxed text-ink-muted">
          <span className="font-semibold text-ink">Privacy firewall on.</span> Phones are masked in lists; full number and address stay hidden unless the role is authorized.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />
        <SnapshotBadge active={isFiltered} />
      </div>

      {tab !== "inbox" && (
        <div className="rounded-xl border border-border/70 bg-surface px-3 py-2.5">
          <FilterBar />
        </div>
      )}

      {tab === "inbox" ? (
        <WhatsAppInbox />
      ) : tab === "pending" ? (
        pending.length === 0 ? <EmptyState icon={Reply} title="No pending replies" description="Conversations waiting on a customer reply appear here." /> : <RecordList>{pending.map(convCard)}</RecordList>
      ) : tab === "takeover" ? (
        takeover.length === 0 ? <EmptyState icon={Hand} title="No human takeovers" description="Conversations an operator has taken over appear here." /> : <RecordList>{takeover.map(convCard)}</RecordList>
      ) : tab === "tickets" ? (
        fTickets.length === 0 ? <EmptyState icon={LifeBuoy} title="No tickets" description="Support tickets and concerns appear here." /> : <RecordList>{fTickets.map(ticketCard)}</RecordList>
      ) : tab === "complaints" ? (
        complaints.length === 0 ? <EmptyState icon={SearchX} title="No complaints" description="Damage, quality and lost-item complaints appear here." /> : <RecordList>{complaints.map(ticketCard)}</RecordList>
      ) : tab === "escalations" ? (
        escalations.length === 0 ? <EmptyState icon={Flame} title="No escalations" description="Urgent tickets escalated for a human appear here." /> : <RecordList>{escalations.map(ticketCard)}</RecordList>
      ) : tab === "cancellations" ? (
        fCancellations.length === 0 ? <EmptyState icon={Ban} title="No cancellations" description="Cancellation requests awaiting a decision appear here." /> : (
          <RecordList>
            {fCancellations.map((c) => (
              <CompactRecordCard
                key={c.id}
                id={c.id}
                title={c.customer}
                status={{ label: c.status, tone: c.status === "Approved" ? "success" : c.status === "Declined" ? "danger" : "warning" }}
                fields={[
                  { label: "Order", value: <span className="font-mono">{c.orderId}</span> },
                  { label: "Refund", value: c.refund > 0 ? formatCurrency(c.refund) : "None" },
                  { label: "Reason", value: c.reason },
                ]}
                meta={<span className="hidden text-xxs text-ink-faint sm:block">{formatRelativeTime(c.requestedAt)}</span>}
                href={`/operations/customer-orders/${c.orderId}`}
              />
            ))}
          </RecordList>
        )
      ) : (
        fFollowups.length === 0 ? <EmptyState icon={PhoneCall} title="No follow-ups" description="Scheduled and due customer check-ins appear here." /> : (
          <RecordList>
            {fFollowups.map((f) => (
              <CompactRecordCard
                key={f.id}
                id={f.id}
                title={f.customer}
                status={{ label: f.status, tone: f.status === "Due" ? "warning" : f.status === "Done" ? "success" : "info" }}
                fields={[
                  { label: "City", value: f.city },
                  { label: "Channel", value: f.channel },
                  { label: "Reason", value: f.reason },
                ]}
                meta={<span className="hidden text-xxs text-ink-faint sm:block">{formatRelativeTime(f.due)}</span>}
                onClick={() => setTab("inbox")}
              />
            ))}
          </RecordList>
        )
      )}
    </div>
  );
}
