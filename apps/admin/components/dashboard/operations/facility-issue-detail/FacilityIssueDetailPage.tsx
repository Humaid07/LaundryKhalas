"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, AlertTriangle, ShieldCheck, Building2, MessagesSquare, Send, Lock,
  UserCog, RefreshCw, Radio,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  StatusBadge, EmptyState, LoadingState,
} from "@/components/dashboard/minimal";
import { Button } from "@/components/dashboard/ui/Button";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import {
  severityTone, facilityIssueStatusTone, titleCaseStatus,
} from "@/lib/dashboard/operations-data";
import { priorityTone } from "@/lib/dashboard/status-maps";
import type { Tone } from "@/lib/dashboard/types";
import {
  agentApi, AgentApiError,
  type FacilityIssueDTO, type FacilityIssueMessageDTO,
} from "@/lib/dashboard/whatsapp-agent-api";
import { LIVE_WHATSAPP_ENABLED, useLiveAgentData } from "@/components/dashboard/operations/live/useLiveAgentData";

const severityToneOf = (s: string): Tone => severityTone[titleCaseStatus(s)] ?? "neutral";
const statusToneOf = (s: string): Tone => facilityIssueStatusTone[s] ?? "neutral";
const priorityToneOf = (p: string): Tone => priorityTone[titleCaseStatus(p)] ?? "neutral";

/** Lifecycle transitions the internal team can apply (initial `open` excluded). */
const STATUS_ACTIONS: { label: string; status: string }[] = [
  { label: "Acknowledge", status: "acknowledged" },
  { label: "Waiting on facility", status: "waiting_on_facility" },
  { label: "Waiting on internal team", status: "waiting_on_internal_team" },
  { label: "Resolve", status: "resolved" },
  { label: "Close", status: "closed" },
];

const fieldInput =
  "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40";

function GuardFrame({ backHref, children }: { backHref: string; children: React.ReactNode }) {
  return (
    <div className="lk-enter space-y-8">
      <Link href={backHref} className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted transition-colors hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" /> Facility Facing
      </Link>
      <div className="flex min-h-[40vh] items-center justify-center">{children}</div>
    </div>
  );
}

function ThreadMessage({ m }: { m: FacilityIssueMessageDTO }) {
  if (m.sender_type === "system") {
    return (
      <div className="flex justify-center">
        <span className="rounded-full bg-surface-2 px-3 py-1 text-xxs text-ink-muted">{m.message}</span>
      </div>
    );
  }
  const mine = m.sender_type === "internal"; // internal team on the right
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm shadow-card",
          m.is_internal
            ? "border border-warning/30 bg-warning/[0.08] text-ink"
            : mine
              ? "bg-rose text-rose-contrast"
              : "border border-border bg-surface-2 text-ink",
        )}
      >
        <div className={cn("mb-1 flex items-center gap-1.5 text-xxs font-semibold", mine && !m.is_internal ? "opacity-90" : "opacity-70")}>
          {m.is_internal && <Lock className="h-3 w-3" />}
          <span>{m.sender_label}</span>
          {m.is_internal && <span>· Internal note</span>}
        </div>
        <p className="whitespace-pre-wrap break-words">{m.message}</p>
        <div className="mt-1 text-right text-[10px] opacity-60">{formatRelativeTime(m.created_at)}</div>
      </div>
    </div>
  );
}

/**
 * Full-page detail + thread for a facility-raised issue. Reads from the agent
 * backend (Dashboard → FastAPI) and lets the internal team reply (with an
 * internal-note toggle), change status, and assign an owner. PII-free: facility
 * name + business order ref only — no customer phone/email/address.
 */
export function FacilityIssueDetailPage({ issueId, backHref }: { issueId: string; backHref: string }) {
  const issue = useLiveAgentData<FacilityIssueDTO>(() => agentApi.getFacilityIssue(issueId), [issueId]);
  const thread = useLiveAgentData<FacilityIssueMessageDTO[]>(() => agentApi.getFacilityIssueMessages(issueId), [issueId]);

  const [reply, setReply] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [owner, setOwner] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadedOwner = issue.data?.assigned_internal_owner ?? "";
  useEffect(() => {
    setOwner(loadedOwner);
  }, [loadedOwner]);

  const toMessage = (e: unknown, fallback: string) => (e instanceof AgentApiError ? e.message : fallback);

  async function submitReply() {
    if (!reply.trim() || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await agentApi.replyFacilityIssue(issueId, reply.trim(), isInternal);
      setReply("");
      thread.refresh();
    } catch (e) {
      setActionError(toMessage(e, "Could not send the reply."));
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: string) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await agentApi.setFacilityIssueStatus(issueId, status);
      issue.refresh();
      thread.refresh();
    } catch (e) {
      setActionError(toMessage(e, "Could not update the status."));
    } finally {
      setBusy(false);
    }
  }

  async function assignOwner() {
    const name = owner.trim();
    if (!name || busy || !issue.data) return;
    setBusy(true);
    setActionError(null);
    try {
      await agentApi.setFacilityIssueStatus(issueId, issue.data.status, name);
      issue.refresh();
    } catch (e) {
      setActionError(toMessage(e, "Could not assign the owner."));
    } finally {
      setBusy(false);
    }
  }

  if (!LIVE_WHATSAPP_ENABLED) {
    return (
      <GuardFrame backHref={backHref}>
        <EmptyState
          icon={Radio}
          title="Live data is off"
          description="Facility issues load from the live backend. Enable NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX to view this thread."
        />
      </GuardFrame>
    );
  }
  if (issue.loading) {
    return <GuardFrame backHref={backHref}><LoadingState label="Loading issue…" /></GuardFrame>;
  }
  if (issue.error) {
    return (
      <GuardFrame backHref={backHref}>
        <EmptyState
          icon={AlertTriangle}
          title="Backend unavailable"
          description={issue.error}
          action={<Button size="sm" variant="secondary" onClick={issue.refresh}>Try again</Button>}
        />
      </GuardFrame>
    );
  }
  const data = issue.data;
  if (!data) {
    return (
      <GuardFrame backHref={backHref}>
        <EmptyState icon={AlertTriangle} title="Issue not found" description={`No facility issue matches “${issueId}”.`} action={<Link href={backHref}><Button size="sm" variant="primary">Back to Facility Facing</Button></Link>} />
      </GuardFrame>
    );
  }

  const messages = thread.data ?? [];

  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Facility Facing"
      eyebrow="Facility issue"
      title={data.title}
      status={
        <>
          <StatusBadge tone={severityToneOf(data.severity)} dot={false}>{titleCaseStatus(data.severity)}</StatusBadge>
          <StatusBadge tone={statusToneOf(data.status)} dot={false}>{titleCaseStatus(data.status)}</StatusBadge>
        </>
      }
      actions={
        <Button size="sm" variant="secondary" onClick={() => { issue.refresh(); thread.refresh(); }} aria-label="Refresh issue">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      }
    >
      {actionError && (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/[0.06] px-3.5 py-2.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <p className="text-sm text-danger">{actionError}</p>
        </div>
      )}

      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Issue" icon={AlertTriangle}>
              <FieldGrid>
                <Field label="Facility" value={data.facility_name} />
                <Field label="Order" value={data.order_ref ?? "—"} mono />
                <Field label="Issue type" value={titleCaseStatus(data.issue_type)} />
                <Field label="Raised" value={formatRelativeTime(data.created_at)} />
              </FieldGrid>
              <p className="mt-4 whitespace-pre-wrap break-words border-t border-border/60 pt-4 text-sm text-ink-muted">{data.message}</p>
            </DetailSectionCard>

            <DetailSectionCard title="Conversation" icon={MessagesSquare}>
              {thread.loading ? (
                <LoadingState label="Loading messages…" />
              ) : thread.error ? (
                <EmptyState icon={AlertTriangle} title="Could not load messages" description={thread.error} action={<Button size="sm" variant="secondary" onClick={thread.refresh}>Try again</Button>} />
              ) : messages.length === 0 ? (
                <EmptyState icon={MessagesSquare} title="No messages yet" description="Replies between the facility and the internal team appear here." />
              ) : (
                <div className="space-y-3">
                  {messages.map((m) => <ThreadMessage key={m.id} m={m} />)}
                </div>
              )}

              <div className="mt-5 space-y-2.5 border-t border-border/60 pt-4">
                <textarea
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  rows={3}
                  className={fieldInput}
                  placeholder={isInternal ? "Add an internal note (not shown to the facility)…" : "Reply to the facility…"}
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <label className="flex items-center gap-2 text-xs text-ink-muted">
                    <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} className="h-3.5 w-3.5 accent-rose" />
                    <span className="inline-flex items-center gap-1"><Lock className="h-3 w-3" /> Internal note (not visible to facility)</span>
                  </label>
                  <Button size="sm" variant="primary" onClick={submitReply} disabled={busy || !reply.trim()}>
                    <Send className="h-3.5 w-3.5" /> {isInternal ? "Add note" : "Send reply"}
                  </Button>
                </div>
              </div>
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Details" icon={Building2}>
              <FieldGrid cols={2}>
                <Field label="Severity" value={<Chip tone={severityToneOf(data.severity)}>{titleCaseStatus(data.severity)}</Chip>} />
                <Field label="Priority" value={<Chip tone={priorityToneOf(data.priority)}>{titleCaseStatus(data.priority)}</Chip>} />
                <Field label="Status" value={<Chip tone={statusToneOf(data.status)}>{titleCaseStatus(data.status)}</Chip>} />
                <Field label="Owner" value={data.assigned_internal_owner ?? "Unassigned"} />
              </FieldGrid>
            </DetailSectionCard>

            <DetailSectionCard title="Update status" icon={RefreshCw}>
              <div className="flex flex-wrap gap-2">
                {STATUS_ACTIONS.map((a) => (
                  <Button
                    key={a.status}
                    size="sm"
                    variant={a.status === "resolved" ? "primary" : "secondary"}
                    onClick={() => changeStatus(a.status)}
                    disabled={busy || data.status === a.status}
                  >
                    {a.label}
                  </Button>
                ))}
              </div>
            </DetailSectionCard>

            <DetailSectionCard title="Assign owner" icon={UserCog}>
              <div className="space-y-2.5">
                <input
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  className={fieldInput}
                  placeholder="Internal owner name"
                />
                <Button size="sm" variant="secondary" onClick={assignOwner} disabled={busy || !owner.trim() || owner.trim() === loadedOwner}>
                  <UserCog className="h-3.5 w-3.5" /> Assign
                </Button>
              </div>
            </DetailSectionCard>

            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Facility issue — facility name and order reference only. No customer name, phone, email, full address or payment details.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
