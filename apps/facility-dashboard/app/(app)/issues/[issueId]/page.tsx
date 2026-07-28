"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send, CheckCircle2, Package } from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import { issueStatusTone, issueStatusLabel, statusToken } from "@/lib/status";
import { DetailPageShell } from "@/components/minimal/DetailPageShell";
import { DetailSectionCard, Field, FieldGrid } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

export default function IssueDetailPage({ params }: { params: Promise<{ issueId: string }> }) {
  const { issueId } = use(params);
  const qc = useQueryClient();

  const issue = useQuery({
    queryKey: ["facility", "issue", issueId],
    queryFn: () => facilityApi.issue(issueId),
  });
  const messages = useQuery({
    queryKey: ["facility", "issue", issueId, "messages"],
    queryFn: () => facilityApi.issueMessages(issueId),
  });

  const [text, setText] = useState("");

  const sendMutation = useMutation({
    mutationFn: (message: string) => facilityApi.postIssueMessage(issueId, message),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["facility", "issue", issueId, "messages"] });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => facilityApi.resolveIssue(issueId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["facility", "issue", issueId] });
      qc.invalidateQueries({ queryKey: ["facility", "issues"] });
    },
  });

  if (issue.isLoading) return <LoadingState label="Loading issue…" />;
  if (issue.isError || !issue.data) {
    return <ErrorState description="Could not load this issue." onRetry={() => issue.refetch()} />;
  }

  const iss = issue.data;
  const resolved = statusToken(iss.status) === "resolved";
  const thread = messages.data ?? [];

  return (
    <DetailPageShell
      backHref="/issues"
      backLabel="Back to issues"
      eyebrow="Issue"
      title={iss.title ?? iss.issue_type ?? "Issue"}
      status={
        <StatusBadge tone={issueStatusTone(iss.status)} dot={false}>
          {issueStatusLabel(iss.status)}
        </StatusBadge>
      }
      actions={
        !resolved ? (
          <Button variant="primary" size="lg" disabled={resolveMutation.isPending} onClick={() => resolveMutation.mutate()}>
            {resolveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Resolve
          </Button>
        ) : undefined
      }
    >
      <DetailSectionCard title="Details">
        <FieldGrid cols={3}>
          <Field label="Type" value={iss.issue_type ?? "—"} />
          <Field label="Priority" value={iss.priority ?? "—"} />
          <Field label="Raised" value={formatDateTime(iss.created_at)} />
        </FieldGrid>
        {iss.message && (
          <div className="mt-4 rounded-lg border border-border/60 bg-surface-2 px-3.5 py-3">
            <p className="text-sm text-ink">{iss.message}</p>
          </div>
        )}
        {iss.related_order_id && (
          <Link
            href={`/orders/${iss.related_order_id}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-muted transition-colors hover:text-rose"
          >
            <Package className="h-3.5 w-3.5" /> View related order
          </Link>
        )}
      </DetailSectionCard>

      <DetailSectionCard title="Conversation">
        {messages.isLoading ? (
          <LoadingState label="Loading messages…" />
        ) : thread.length === 0 ? (
          <p className="text-sm text-ink-muted">No messages yet. Start the conversation below.</p>
        ) : (
          <ul className="space-y-3">
            {thread.map((m, i) => {
              const mine = (m.author_type ?? "facility") === "facility";
              return (
                <li key={m.id ?? i} className={cn("flex", mine ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[80%] rounded-2xl px-3.5 py-2.5",
                      mine
                        ? "rounded-br-sm bg-rose text-rose-contrast"
                        : "rounded-bl-sm border border-border bg-surface-2 text-ink",
                    )}
                  >
                    <p className="text-sm">{m.message}</p>
                    <p className={cn("mt-1 text-[10px]", mine ? "text-rose-contrast/70" : "text-ink-faint")}>
                      {m.author_name ? `${m.author_name} · ` : mine ? "" : "Operations · "}
                      {formatDateTime(m.created_at)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {!resolved && (
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && text.trim()) sendMutation.mutate(text.trim());
              }}
              placeholder="Write a message…"
              className="h-11 flex-1 rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
            <Button
              variant="primary"
              size="lg"
              disabled={!text.trim() || sendMutation.isPending}
              onClick={() => sendMutation.mutate(text.trim())}
            >
              {sendMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </Button>
          </div>
        )}
      </DetailSectionCard>
    </DetailPageShell>
  );
}
