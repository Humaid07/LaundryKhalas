"use client";

import { Boxes, GitBranch, RotateCw, Play, Ban, ScrollText, RefreshCw, AlertTriangle, ShieldCheck } from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import { jobStatusTone, JOB_LIFECYCLE, type JobRow } from "@/lib/dashboard/dev-automation-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

/** Detail-page actions for a background job. Retry/requeue are approval-gated
 * (RULE 13); nothing performs a live action in mock mode. */
const ACTIONS = (j: JobRow): MenuItem[] => [
  { label: "Retry job", icon: RotateCw, approval: true, disabled: j.status !== "Failed" && j.status !== "Retrying" },
  { label: "Run now", icon: Play, disabled: j.status === "Running" },
  { label: "Requeue", icon: RefreshCw, approval: true, disabled: j.status === "Running" },
  { label: "View logs", icon: ScrollText },
  { label: "Raise issue", icon: AlertTriangle },
  { label: "Cancel job", icon: Ban, tone: "danger", approval: true, disabled: j.status === "Done" },
];

function ProgressCard({ job }: { job: JobRow }) {
  const currentIdx = job.status === "Failed" || job.status === "Retrying"
    ? JOB_LIFECYCLE.indexOf("Running")
    : JOB_LIFECYCLE.indexOf(job.status);

  return (
    <DetailSectionCard title="Job progress" icon={GitBranch}>
      {job.status === "Failed" ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/8 px-3.5 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <p className="text-sm text-danger">Job failed after {job.attempts} attempt{job.attempts === 1 ? "" : "s"}{job.error !== "—" ? ` — ${job.error}` : ""}. Retry when the underlying issue is cleared.</p>
        </div>
      ) : (
        <ol className="space-y-3">
          {JOB_LIFECYCLE.map((s, i) => {
            const done = currentIdx >= 0 && i <= currentIdx;
            const current = s === job.status;
            return (
              <li key={s} className="flex gap-3">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${done ? "bg-rose" : "bg-ink-faint/40"}`} />
                <div className="min-w-0">
                  <p className="text-sm text-ink">{s}</p>
                  {current && <p className="text-xxs text-ink-faint">Current stage</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </DetailSectionCard>
  );
}

export function JobDetailPage({ job, backHref }: { job: JobRow; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Job queue"
      eyebrow="Background job"
      title={<span className="font-mono">{job.name}</span>}
      status={<StatusBadge tone={jobStatusTone[job.status]} dot={false}>{job.status}</StatusBadge>}
      actions={<ActionMenu items={ACTIONS(job)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Job" icon={Boxes}>
              <FieldGrid>
                <Field label="Name" value={job.name} mono />
                <Field label="Agent" value={job.agent} />
                <Field label="Status" value={<Chip tone={jobStatusTone[job.status]}>{job.status}</Chip>} />
                <Field label="Attempts" value={job.attempts} />
                <Field label="Queued at" value={fmtTime(job.queuedAt)} />
                <Field label="Next retry" value={fmtTime(job.nextRetry)} />
              </FieldGrid>
            </DetailSectionCard>
            <ProgressCard job={job} />
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Last error" icon={AlertTriangle}>
              {job.error === "—" ? (
                <p className="text-sm text-ink-muted">No errors recorded for this job.</p>
              ) : (
                <p className="text-sm text-danger">{job.error}</p>
              )}
            </DetailSectionCard>
            <DetailSectionCard title="Safety" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Safe summary only — no secrets, tokens or raw payloads. Retry, requeue and cancel require human approval before they take effect.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
