"use client";

import { RefreshCw, Radio, AlertTriangle, MessagesSquare, Flag, ShieldAlert } from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import type { Tone } from "@/lib/dashboard/types";
import {
  agentApi,
  type InboxConversationDTO,
  type AgentFlagDTO,
} from "@/lib/dashboard/whatsapp-agent-api";
import { LIVE_WHATSAPP_ENABLED, useLiveAgentData } from "./useLiveAgentData";

function priorityTone(priority: string | null): Tone {
  switch ((priority || "").toLowerCase()) {
    case "urgent": return "danger";
    case "high": return "warning";
    case "medium": return "info";
    default: return "neutral";
  }
}

function statusTone(status: string): Tone {
  switch (status) {
    case "human_needed": return "warning";
    case "human_takeover": return "info";
    case "resolved": return "success";
    default: return "neutral";
  }
}

const convoColumns: Column<InboxConversationDTO>[] = [
  { key: "customer", header: "Customer", primary: true, cell: (c) => <span className="whitespace-nowrap text-ink">{c.customer_name ?? "WhatsApp customer"}</span> },
  // Privacy: masked phone only — the full number never leaves the backend.
  { key: "phone", header: "Phone", cell: (c) => <span className="whitespace-nowrap font-mono text-xs text-ink-muted">{c.masked_phone ?? "•••• ••••"}</span> },
  { key: "geo", header: "City / Area", cell: (c) => <span className="whitespace-nowrap text-xs text-ink-muted">{[c.area, c.city].filter(Boolean).join(", ") || "—"}</span> },
  { key: "status", header: "Status", cell: (c) => <StatusBadge tone={statusTone(c.status)}>{c.status.replace(/_/g, " ")}</StatusBadge> },
  { key: "priority", header: "Priority", cell: (c) => (c.priority ? <StatusBadge tone={priorityTone(c.priority)} dot={false}>{c.priority}</StatusBadge> : <span className="text-xs text-ink-faint">—</span>) },
  { key: "order", header: "Linked Order", cell: (c) => (c.linked_order_id ? <span className="font-mono text-xs text-ink">{c.linked_order_id}</span> : <span className="text-xs text-ink-faint">—</span>) },
  { key: "last", header: "Last Message", cell: (c) => <span className="block max-w-[16rem] truncate text-xs text-ink-muted">{c.last_message ?? "—"}</span> },
  { key: "unread", header: "Unread", align: "right", cell: (c) => (c.unread_count > 0 ? <StatusBadge tone="info" dot={false}>{c.unread_count}</StatusBadge> : <span className="text-xs text-ink-faint">0</span>) },
];

function FlagsPanel() {
  const { data, loading, error, refresh } = useLiveAgentData<AgentFlagDTO[]>(() => agentApi.listFlags("open"));
  const rows = data ?? [];

  return (
    <Panel>
      <PanelHeader
        title="Human intervention needed"
        subtitle="Open flags raised by the agent · live from /api/flags"
        action={<StatusBadge tone={rows.length ? "warning" : "success"}>{rows.length} open</StatusBadge>}
      />
      {loading ? (
        <LoadingState label="Loading flags…" />
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Backend unavailable" description={error} action={<Button size="sm" variant="secondary" onClick={refresh}>Try again</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={ShieldAlert} title="No open flags" description="Refunds, complaints and other escalations will appear here for review." />
      ) : (
        <ul className="space-y-2.5">
          {rows.map((f) => (
            <li key={f.id} className="flex flex-col gap-2 rounded-xl border border-warning/25 bg-warning/8 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-2.5">
                <Flag className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                <div>
                  <p className="text-sm text-ink">{f.flag_type.replace(/_/g, " ")}{f.order_id ? <span className="ml-1 font-mono text-xs text-ink-muted">· order linked</span> : null}</p>
                  <p className="text-xs text-ink-muted">{f.reason ?? "—"}</p>
                  {f.assigned_team && <p className="text-xxs text-ink-faint">Team: {f.assigned_team}</p>}
                </div>
              </div>
              <StatusBadge tone={priorityTone(f.priority)} dot={false}>{f.priority ?? "—"}</StatusBadge>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/**
 * Live WhatsApp conversations + open flags, read from the agent backend
 * (Dashboard → FastAPI → Supabase). Rendered only when
 * NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true. Phones are masked; full number and
 * address never reach the dashboard.
 */
export function LiveWhatsAppConversations() {
  const { data, loading, error, refresh } = useLiveAgentData<InboxConversationDTO[]>(() => agentApi.listConversations());
  if (!LIVE_WHATSAPP_ENABLED) return null;

  const rows = data ?? [];

  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader
          title="Live WhatsApp conversations"
          subtitle="Real inbound conversations · live from /api/conversations"
          className="p-4"
          action={
            <div className="flex items-center gap-2">
              <StatusBadge tone="info" dot><span className="inline-flex items-center gap-1"><Radio className="h-3 w-3" /> Live</span></StatusBadge>
              <Button size="sm" variant="secondary" onClick={refresh} aria-label="Refresh live conversations">
                <RefreshCw className="h-3.5 w-3.5" /> Refresh
              </Button>
            </div>
          }
        />
        <div className="px-4 pb-4">
          {loading ? (
            <LoadingState label="Loading live conversations…" />
          ) : error ? (
            <EmptyState icon={AlertTriangle} title="Backend unavailable" description={error} action={<Button size="sm" variant="secondary" onClick={refresh}>Try again</Button>} />
          ) : (
            <DataTable
              columns={convoColumns}
              rows={rows}
              rowKey={(c) => c.id}
              empty={<EmptyState icon={MessagesSquare} title="No live conversations yet" description="Approved WhatsApp customers will appear here as they message the agent." />}
              onRowLabel={(c) => <StatusBadge tone={statusTone(c.status)}>{c.status.replace(/_/g, " ")}</StatusBadge>}
            />
          )}
        </div>
      </Panel>
      <FlagsPanel />
    </div>
  );
}
