"use client";

import {
  Building2, GitBranch, ShieldCheck, UserCog, ArrowRightLeft, CalendarClock,
  StickyNote, CheckCircle2, XCircle, Gauge, MapPin, FileCheck2, CalendarDays,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  stageTone, complianceTone, docStateTone,
  type Partner, type ComplianceRow, type MeetingRow, type DocState,
} from "@/lib/dashboard/partner-acquisition-data";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { Tone } from "@/lib/dashboard/types";
import { LEAD_LIFECYCLE } from "./data";

const fmtTime = (iso: string) => (iso === "—" ? "—" : formatRelativeTime(iso));

function scoreTone(n: number): Tone {
  return n >= 80 ? "success" : n >= 65 ? "rose" : n >= 45 ? "warning" : "neutral";
}

/* Record actions live ONLY here — approval-gated where they commit a partner
 * decision (RULE 13). Mock only: no handlers wired. */
const ACTIONS = (p: Partner): MenuItem[] => {
  const active = p.stage === "Active Partner";
  const rejected = p.stage === "Rejected / Not Fit";
  return [
    { label: "Assign owner", icon: UserCog },
    { label: "Schedule follow-up", icon: CalendarClock, disabled: rejected },
    { label: "Move stage", icon: ArrowRightLeft, disabled: rejected },
    { label: "Request compliance review", icon: ShieldCheck, approval: true, disabled: rejected },
    { label: "Add note", icon: StickyNote },
    { label: "Mark onboarded", icon: CheckCircle2, approval: true, disabled: active || rejected },
    { label: "Reject lead", icon: XCircle, tone: "danger", approval: true, disabled: active || rejected },
  ];
};

function ProgressCard({ partner }: { partner: Partner }) {
  if (partner.stage === "Rejected / Not Fit") {
    return (
      <DetailSectionCard title="Pipeline progress" icon={GitBranch}>
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/8 px-3.5 py-3">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <p className="text-sm text-danger">Lead archived as not a fit — {partner.nextStep}</p>
        </div>
      </DetailSectionCard>
    );
  }
  const currentIdx = LEAD_LIFECYCLE.indexOf(partner.stage);
  return (
    <DetailSectionCard title="Pipeline progress" icon={GitBranch}>
      <ol className="space-y-3">
        {LEAD_LIFECYCLE.map((s, i) => {
          const done = currentIdx >= 0 && i <= currentIdx;
          const current = s === partner.stage;
          return (
            <li key={s} className="flex gap-3">
              <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${done ? "bg-rose" : "bg-ink-faint/40"}`} />
              <div className="min-w-0">
                <p className={`text-sm ${done ? "text-ink" : "text-ink-muted"}`}>{s}</p>
                {current && <p className="text-xxs text-ink-faint">Current stage</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </DetailSectionCard>
  );
}

function DocRow({ label, state }: { label: string; state: DocState }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-sm text-ink-muted">{label}</span>
      <Chip tone={docStateTone[state]}>{state}</Chip>
    </div>
  );
}

function ComplianceCard({ compliance }: { compliance: ComplianceRow }) {
  return (
    <DetailSectionCard title="Compliance" icon={FileCheck2}>
      <div className="divide-y divide-border/60">
        <DocRow label="Trade license" state={compliance.tradeLicense} />
        <DocRow label="Bank / payout" state={compliance.bankPayout} />
        <DocRow label="Quality checklist" state={compliance.qualityChecklist} />
        <DocRow label="Agreement" state={compliance.agreement} />
        <DocRow label="Insurance / docs" state={compliance.insurance} />
      </div>
      <p className="mt-3 flex items-center gap-1.5 border-t border-border/60 pt-3 text-xxs text-ink-faint">
        <ShieldCheck className="h-3 w-3" /> Status-only — no document contents or account numbers stored.
      </p>
    </DetailSectionCard>
  );
}

export function PartnerLeadDetailPage({
  partner,
  compliance,
  meetings,
  backHref,
}: {
  partner: Partner;
  compliance?: ComplianceRow;
  meetings: MeetingRow[];
  backHref: string;
}) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Pipeline"
      eyebrow="Partner lead"
      title={partner.name}
      status={
        <>
          <StatusBadge tone={stageTone[partner.stage]} dot={false}>{partner.stage}</StatusBadge>
          <StatusBadge tone={complianceTone[partner.compliance]} dot={false}>{partner.compliance}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(partner)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Lead overview" icon={Building2}>
              <FieldGrid>
                <Field label="Partner ID" value={partner.id} mono />
                <Field label="Type" value={partner.type} />
                <Field label="Region" value={partner.region} />
                <Field label="Location" value={`${partner.city}, ${partner.country}`} />
                <Field label="Last contact" value={fmtTime(partner.lastContact)} />
                <Field label="Next step" value={partner.nextStep} />
              </FieldGrid>
            </DetailSectionCard>
            <ProgressCard partner={partner} />
            {compliance && <ComplianceCard compliance={compliance} />}
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Ownership" icon={UserCog}>
              <FieldGrid cols={2}>
                <Field label="Owner" value={partner.owner} />
                <Field
                  label="Score"
                  value={<Chip tone={scoreTone(partner.score)}>{partner.score}</Chip>}
                />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Compliance status" icon={Gauge}>
              <div className="flex items-center justify-between">
                <span className="text-sm text-ink-muted">Overall</span>
                <Chip tone={complianceTone[partner.compliance]}>{partner.compliance}</Chip>
              </div>
            </DetailSectionCard>
            {meetings.length > 0 && (
              <DetailSectionCard title="Meetings" icon={CalendarDays}>
                <ul className="space-y-3">
                  {meetings.map((m) => (
                    <li key={m.id} className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{m.type}</p>
                      <p className="mt-0.5 text-xxs text-ink-faint">
                        {new Date(m.datetime).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })} · {m.status}
                      </p>
                    </li>
                  ))}
                </ul>
              </DetailSectionCard>
            )}
            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="flex items-start gap-1.5 text-xs leading-relaxed text-ink-muted">
                <MapPin className="mt-0.5 h-3 w-3 shrink-0 text-ink-faint" />
                Business-level data only — no private personal emails or phone numbers stored for this lead.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
