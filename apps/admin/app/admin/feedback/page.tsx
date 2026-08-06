"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Check, Flag, X } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatDateTime } from "@/lib/formatters";
import { agentApi, type FeedbackEventDTO } from "@/lib/dashboard/whatsapp-agent-api";

const STATUSES = ["new", "reviewed", "approved", "rejected", "duplicate"];

export default function FeedbackReviewPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("new");
  const [error, setError] = useState<string | null>(null);

  const feedbackQ = useQuery({
    queryKey: ["agent", "feedback", status],
    queryFn: () => agentApi.listFeedback(status === "all" ? undefined : status),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["agent", "feedback"] });

  const queueGlobal = useMutation({
    mutationFn: (f: FeedbackEventDTO) => agentApi.queueGlobalFeedback(f.id, targetFor(f.feedback_type)),
    onSuccess: () => { setError(null); refresh(); },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not queue for review."),
  });
  const reject = useMutation({
    mutationFn: (id: string) => agentApi.rejectFeedback(id),
    onSuccess: () => { setError(null); refresh(); },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not reject."),
  });

  const rows = feedbackQ.data ?? [];

  return (
    <div>
      <PageHeader
        title="Feedback Review"
        description="Customer feedback captured by the WhatsApp agent. Global feedback never changes behaviour until an authorized review approves it."
        actions={
          <Button variant="secondary" size="sm" onClick={() => feedbackQ.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-sm capitalize text-ink"
        >
          <option value="all">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        {error && <span className="text-sm font-medium text-danger">{error}</span>}
      </Card>

      <Card>
        {feedbackQ.isLoading && <LoadingState label="Loading feedback…" />}
        {feedbackQ.error && !feedbackQ.isLoading && (
          <ErrorState message={(feedbackQ.error as Error).message} onRetry={() => feedbackQ.refetch()} />
        )}
        {!feedbackQ.isLoading && !feedbackQ.error && rows.length === 0 && (
          <EmptyState title="No feedback to review" description="Customer corrections and preferences captured by the agent appear here." />
        )}
        {!feedbackQ.isLoading && !feedbackQ.error && rows.length > 0 && (
          <ul className="divide-y divide-border">
            {rows.map((f) => (
              <li key={f.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{f.feedback_type.replace(/_/g, " ")}</span>
                    <StatusBadge status={f.scope} />
                    <StatusBadge status={f.status} />
                  </div>
                  {f.raw_text && <p className="mt-1 text-sm text-ink-muted">“{f.raw_text}”</p>}
                  <p className="mt-1 text-xs text-ink-faint">
                    {f.order_id ? `Order ${f.order_id.slice(0, 8)} · ` : ""}
                    {formatDateTime(f.created_at)}
                  </p>
                </div>
                {f.status === "new" && (
                  <div className="flex shrink-0 items-center gap-2">
                    {f.scope === "global" ? (
                      <Button size="sm" variant="secondary" disabled={queueGlobal.isPending} onClick={() => queueGlobal.mutate(f)}>
                        <Flag className="h-3.5 w-3.5" /> Queue for review
                      </Button>
                    ) : (
                      <span className="text-xs text-ink-faint">
                        <Check className="mr-1 inline h-3.5 w-3.5" /> Customer scope (apply via memory tools)
                      </span>
                    )}
                    <Button size="sm" variant="ghost" disabled={reject.isPending} onClick={() => reject.mutate(f.id)}>
                      <X className="h-3.5 w-3.5" /> Reject
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/** Map a global feedback type to the config target it would eventually change. */
function targetFor(feedbackType: string): string {
  switch (feedbackType) {
    case "NEGATIVE_RESPONSE_FEEDBACK":
    case "REPEATED_QUESTION_FEEDBACK":
      return "system_prompt";
    case "SERVICE_CLASSIFICATION_FEEDBACK":
      return "classifier";
    case "PRICE_FEEDBACK":
      return "price_rule";
    default:
      return "template";
  }
}
