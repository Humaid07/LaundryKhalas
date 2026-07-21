"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Lock, RefreshCw, Unlock } from "lucide-react";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ChatMessageBubble, AgentDraftBubble } from "@/components/conversations/ChatMessageBubble";
import { ManualReplyBox } from "@/components/conversations/ManualReplyBox";
import { ConversationContextPanel } from "@/components/conversations/ConversationContextPanel";

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const conversationQ = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api.getConversation(id),
  });
  const marketsQ = useQuery({ queryKey: ["markets"], queryFn: api.listMarkets });
  const approvalsQ = useQuery({ queryKey: ["approvals"], queryFn: () => api.listApprovals() });
  const logsQ = useQuery({
    queryKey: ["ai-action-logs", "conversation", id],
    queryFn: () => api.listAiActionLogs({ conversation_id: id }),
  });

  const conversationApprovals = useMemo(
    () => (approvalsQ.data ?? []).filter((a) => a.conversation_id === id),
    [approvalsQ.data, id]
  );
  const pendingApprovals = conversationApprovals.filter((a) => a.status === "pending");
  const pendingReplyDrafts = pendingApprovals.filter((a) => a.action_type === "send_customer_reply");

  const relatedOrderId = useMemo(() => {
    const fromLogs = (logsQ.data ?? []).find((l) => l.order_id)?.order_id;
    if (fromLogs) return fromLogs;
    return conversationApprovals.find((a) => a.order_id)?.order_id ?? null;
  }, [logsQ.data, conversationApprovals]);

  const orderQ = useQuery({
    queryKey: ["order", relatedOrderId],
    queryFn: () => api.getOrder(relatedOrderId as string),
    enabled: !!relatedOrderId,
  });

  const marketCode =
    marketsQ.data?.find((m) => m.id === conversationQ.data?.market_id)?.code ??
    conversationQ.data?.market_id.slice(0, 8) ??
    "-";

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["conversation", id] });
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({ queryKey: ["ai-action-logs"] });
    queryClient.invalidateQueries({ queryKey: ["orders"] });
    if (relatedOrderId) queryClient.invalidateQueries({ queryKey: ["order", relatedOrderId] });
  };

  const runAgentMutation = useMutation({
    mutationFn: () => api.runAgent(id),
    onSuccess: invalidateAll,
  });
  const takeoverMutation = useMutation({
    mutationFn: () => api.manualTakeover(id, "admin"),
    onSuccess: invalidateAll,
  });
  const releaseMutation = useMutation({
    mutationFn: () => api.releaseTakeover(id),
    onSuccess: invalidateAll,
  });
  const manualReplyMutation = useMutation({
    mutationFn: (text: string) => api.manualReply(id, text),
    onSuccess: invalidateAll,
  });
  const approveMutation = useMutation({
    mutationFn: (approvalId: string) => api.approveApproval(approvalId, "admin"),
    onSuccess: invalidateAll,
  });
  const rejectMutation = useMutation({
    mutationFn: (approvalId: string) => api.rejectApproval(approvalId, "admin"),
    onSuccess: invalidateAll,
  });

  const isLoading = conversationQ.isLoading || marketsQ.isLoading;
  const error = conversationQ.error;

  if (isLoading) return <LoadingState label="Loading conversation…" />;
  if (error || !conversationQ.data) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Conversation not found."}
        onRetry={() => conversationQ.refetch()}
      />
    );
  }

  const conversation = conversationQ.data;
  const messages = [...conversation.messages].sort((a, b) => (a.created_at < b.created_at ? -1 : 1));

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => router.push("/admin/conversations")}
          className="flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to inbox
        </button>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={invalidateAll}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
          {conversation.manual_takeover ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => releaseMutation.mutate()}
              disabled={releaseMutation.isPending}
            >
              <Unlock className="h-3.5 w-3.5" />
              Release Takeover
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => takeoverMutation.mutate()}
              disabled={takeoverMutation.isPending}
            >
              <Lock className="h-3.5 w-3.5" />
              Manual Takeover
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={() => runAgentMutation.mutate()}
            disabled={conversation.manual_takeover || runAgentMutation.isPending}
            title={conversation.manual_takeover ? "Release manual takeover first" : undefined}
          >
            <Bot className="h-3.5 w-3.5" />
            Run WhatsApp Agent
          </Button>
        </div>
      </div>

      {runAgentMutation.isError && (
        <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger-text">
          {(runAgentMutation.error as Error).message}
        </p>
      )}
      {conversation.manual_takeover && (
        <p className="mb-3 rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning-text">
          Manual takeover is active. Agent auto-run is disabled - release it to let the agent run again.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <Card className="flex flex-col overflow-hidden">
          <div className="flex-1 space-y-4 overflow-y-auto p-5" style={{ minHeight: 420, maxHeight: 640 }}>
            {messages.length === 0 && pendingReplyDrafts.length === 0 ? (
              <EmptyState title="No messages yet" description="This conversation has no messages." />
            ) : (
              <>
                {messages.map((m) => (
                  <ChatMessageBubble key={m.id} message={m} />
                ))}
                {pendingReplyDrafts.map((draft) => (
                  <AgentDraftBubble
                    key={draft.id}
                    text={draft.proposed_payload_json?.text ?? ""}
                    onApprove={() => approveMutation.mutate(draft.id)}
                    onReject={() => rejectMutation.mutate(draft.id)}
                    isDeciding={approveMutation.isPending || rejectMutation.isPending}
                  />
                ))}
              </>
            )}
          </div>
          <ManualReplyBox
            onSend={(text) => manualReplyMutation.mutate(text)}
            isSending={manualReplyMutation.isPending}
            notice={
              conversation.manual_takeover
                ? "Manual takeover is active - you are in full control of this conversation."
                : "Agent auto-run is enabled. Manual replies bypass the approval queue and send immediately."
            }
          />
        </Card>

        <ConversationContextPanel
          conversation={conversation}
          marketCode={marketCode}
          order={orderQ.data ?? null}
          pendingApprovals={pendingApprovals}
          recentLogs={logsQ.data ?? []}
          onApprove={(approvalId) => approveMutation.mutate(approvalId)}
          onReject={(approvalId) => rejectMutation.mutate(approvalId)}
          isDeciding={approveMutation.isPending || rejectMutation.isPending}
        />
      </div>
    </div>
  );
}
