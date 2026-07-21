"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, X } from "lucide-react";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { AIActionLogTable } from "@/components/logs/AIActionLogTable";
import { shortId } from "@/lib/formatters";

export default function AiLogsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading AI action logs…" />}>
      <AiLogsContent />
    </Suspense>
  );
}

function AiLogsContent() {
  const searchParams = useSearchParams();
  const conversationIdParam = searchParams.get("conversation_id") ?? undefined;
  const orderIdParam = searchParams.get("order_id") ?? undefined;

  const [agent, setAgent] = useState("all");
  const [result, setResult] = useState<"all" | "success" | "failed">("all");

  const logsQ = useQuery({
    queryKey: ["ai-action-logs", "page", conversationIdParam, orderIdParam],
    queryFn: () =>
      api.listAiActionLogs({
        conversation_id: conversationIdParam,
        order_id: orderIdParam,
        limit: "500",
      }),
  });

  const logs = logsQ.data ?? [];
  const agentOptions = ["all", ...Array.from(new Set(logs.map((l) => l.agent_name)))];

  const filtered = logs.filter((l) => {
    if (agent !== "all" && l.agent_name !== agent) return false;
    if (result === "success" && !l.success) return false;
    if (result === "failed" && l.success) return false;
    return true;
  });

  const clearScopeHref = "/admin/ai-logs";
  const scopeLabel = useMemo(() => {
    if (conversationIdParam) return `Conversation ${shortId(conversationIdParam)}`;
    if (orderIdParam) return `Order ${shortId(orderIdParam)}`;
    return null;
  }, [conversationIdParam, orderIdParam]);

  return (
    <div>
      <PageHeader
        title="AI Action Logs"
        description="Every agent decision, tool call, and LLM call - the full audit trail for debugging."
        actions={
          <Button variant="secondary" size="sm" onClick={() => logsQ.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {scopeLabel && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-info-soft px-3 py-2 text-xs text-info-text">
          <span>Filtered to {scopeLabel}</span>
          <a href={clearScopeHref} className="ml-auto flex items-center gap-1 font-medium hover:underline">
            <X className="h-3 w-3" />
            Clear
          </a>
        </div>
      )}

      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <select
          value={agent}
          onChange={(e) => setAgent(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink"
        >
          {agentOptions.map((a) => (
            <option key={a} value={a}>
              {a === "all" ? "All agents" : a}
            </option>
          ))}
        </select>

        <select
          value={result}
          onChange={(e) => setResult(e.target.value as typeof result)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm text-ink"
        >
          <option value="all">All results</option>
          <option value="success">Success only</option>
          <option value="failed">Failed only</option>
        </select>

        <span className="ml-auto text-xs text-ink-faint">{filtered.length} of {logs.length} shown</span>
      </Card>

      <Card>
        {logsQ.isLoading && <LoadingState label="Loading AI action logs…" />}
        {logsQ.error && !logsQ.isLoading && (
          <ErrorState message={(logsQ.error as Error).message} onRetry={() => logsQ.refetch()} />
        )}
        {!logsQ.isLoading && !logsQ.error && filtered.length === 0 && (
          <EmptyState
            title="No AI actions logged"
            description="Run the WhatsApp Agent on a conversation to generate log entries."
          />
        )}
        {!logsQ.isLoading && !logsQ.error && filtered.length > 0 && <AIActionLogTable logs={filtered} />}
      </Card>
    </div>
  );
}
