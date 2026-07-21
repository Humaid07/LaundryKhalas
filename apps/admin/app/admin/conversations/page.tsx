"use client";

import { useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ConversationList, type ConversationRow } from "@/components/conversations/ConversationList";

const STATUS_OPTIONS = ["all", "open", "escalated", "closed"];

export default function ConversationsPage() {
  const [status, setStatus] = useState("all");
  const [market, setMarket] = useState("all");
  const [manualOnly, setManualOnly] = useState(false);
  const [pendingOnly, setPendingOnly] = useState(false);
  const [search, setSearch] = useState("");

  const conversationsQ = useQuery({ queryKey: ["conversations"], queryFn: api.listConversations });
  const marketsQ = useQuery({ queryKey: ["markets"], queryFn: api.listMarkets });
  const approvalsQ = useQuery({ queryKey: ["approvals"], queryFn: () => api.listApprovals() });

  const conversations = conversationsQ.data ?? [];

  const messageQueries = useQueries({
    queries: conversations.map((c) => ({
      queryKey: ["messages", c.id],
      queryFn: () => api.listMessages(c.id),
      enabled: conversations.length > 0,
    })),
  });

  const isLoading =
    conversationsQ.isLoading ||
    marketsQ.isLoading ||
    approvalsQ.isLoading ||
    messageQueries.some((q) => q.isLoading);
  const error = conversationsQ.error || marketsQ.error || approvalsQ.error;

  const refetchAll = () => {
    conversationsQ.refetch();
    marketsQ.refetch();
    approvalsQ.refetch();
    messageQueries.forEach((q) => q.refetch());
  };

  const marketCodeById = useMemo(() => {
    const map = new Map<string, string>();
    (marketsQ.data ?? []).forEach((m) => map.set(m.id, m.code));
    return map;
  }, [marketsQ.data]);

  const pendingConversationIds = useMemo(() => {
    const set = new Set<string>();
    (approvalsQ.data ?? []).forEach((a) => {
      if (a.status === "pending" && a.conversation_id) set.add(a.conversation_id);
    });
    return set;
  }, [approvalsQ.data]);

  const rows: ConversationRow[] = useMemo(
    () =>
      conversations.map((c, idx) => {
        const messages = messageQueries[idx]?.data ?? [];
        const latest = messages[messages.length - 1];
        return {
          ...c,
          marketCode: marketCodeById.get(c.market_id) ?? c.market_id.slice(0, 8),
          latestMessagePreview: latest?.text ?? null,
          hasPendingApproval: pendingConversationIds.has(c.id),
        };
      }),
    [conversations, messageQueries, marketCodeById, pendingConversationIds]
  );

  const filteredRows = rows.filter((row) => {
    if (status !== "all" && row.status !== status) return false;
    if (market !== "all" && row.marketCode !== market) return false;
    if (manualOnly && !row.manual_takeover) return false;
    if (pendingOnly && !row.hasPendingApproval) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      const haystack = `${row.customer_id} ${row.latestMessagePreview ?? ""}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  return (
    <div>
      <PageHeader
        title="Conversations"
        description="All WhatsApp conversations handled by the agent."
        actions={
          <Button variant="secondary" size="sm" onClick={refetchAll}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : s}
            </option>
          ))}
        </select>

        <select
          value={market}
          onChange={(e) => setMarket(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink"
        >
          <option value="all">All markets</option>
          {(marketsQ.data ?? []).map((m) => (
            <option key={m.id} value={m.code}>
              {m.code}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1.5 text-sm text-ink-muted">
          <input type="checkbox" checked={manualOnly} onChange={(e) => setManualOnly(e.target.checked)} />
          Manual takeover only
        </label>

        <label className="flex items-center gap-1.5 text-sm text-ink-muted">
          <input type="checkbox" checked={pendingOnly} onChange={(e) => setPendingOnly(e.target.checked)} />
          Pending approval only
        </label>

        <input
          type="search"
          placeholder="Search by customer id or message…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto min-w-[220px] flex-1 rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint"
        />
      </Card>

      <Card>
        {isLoading && <LoadingState label="Loading conversations…" />}
        {error && !isLoading && <ErrorState message={(error as Error).message} onRetry={refetchAll} />}
        {!isLoading && !error && filteredRows.length === 0 && (
          <EmptyState
            title="No conversations match your filters"
            description="Try clearing filters, or send a new inbound message from the WhatsApp Console."
          />
        )}
        {!isLoading && !error && filteredRows.length > 0 && <ConversationList rows={filteredRows} />}
      </Card>
    </div>
  );
}
