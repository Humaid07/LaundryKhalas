"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";

const TABS = ["pending", "approved", "rejected", "all"] as const;

export default function ApprovalsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("pending");
  const queryClient = useQueryClient();

  const approvalsQ = useQuery({
    queryKey: ["approvals", tab],
    queryFn: () => api.listApprovals(tab === "all" ? undefined : tab),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({ queryKey: ["conversation"] });
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
    queryClient.invalidateQueries({ queryKey: ["ai-action-logs"] });
  };

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.approveApproval(id, "admin"),
    onSuccess: invalidate,
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.rejectApproval(id, "admin"),
    onSuccess: invalidate,
  });

  const approvals = approvalsQ.data ?? [];
  const isDeciding = approveMutation.isPending || rejectMutation.isPending;

  return (
    <div>
      <PageHeader
        title="Approval Queue"
        description="This is the safety gate - agent-drafted replies only reach the customer once approved here."
        actions={
          <Button variant="secondary" size="sm" onClick={() => approvalsQ.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <div className="mb-4 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-2 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "border-brand text-brand"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {approvalsQ.isLoading && <LoadingState label="Loading approvals…" />}
      {approvalsQ.error && !approvalsQ.isLoading && (
        <ErrorState message={(approvalsQ.error as Error).message} onRetry={() => approvalsQ.refetch()} />
      )}
      {!approvalsQ.isLoading && !approvalsQ.error && approvals.length === 0 && (
        <Card>
          <EmptyState
            title={`No ${tab === "all" ? "" : tab} approvals`}
            description="Run the WhatsApp Agent on a conversation to generate a draft reply that needs your approval."
          />
        </Card>
      )}
      {!approvalsQ.isLoading && !approvalsQ.error && approvals.length > 0 && (
        <div className="space-y-3">
          {approvals.map((a) => (
            <ApprovalCard
              key={a.id}
              approval={a}
              onApprove={() => approveMutation.mutate(a.id)}
              onReject={() => rejectMutation.mutate(a.id)}
              isDeciding={isDeciding}
            />
          ))}
        </div>
      )}
    </div>
  );
}
