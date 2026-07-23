import type { LucideIcon } from "lucide-react";
import {
  BarChart3, TrendingUp, AlertTriangle, ArrowRight, Info, Download,
  FileText, Share2, CalendarClock, Sparkles,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import type { ReportDetail } from "@/lib/dashboard/reports-data";
import { getReportTitle } from "@/lib/dashboard/reports-data";

const ACTIONS: MenuItem[] = [
  { label: "Export PDF", icon: FileText },
  { label: "Export CSV", icon: Download },
  { label: "Share link", icon: Share2 },
  { label: "Schedule delivery", icon: CalendarClock },
];

/** A quiet bulleted list for a report narrative section. */
function BulletList({ items, dot }: { items: string[]; dot: string }) {
  if (items.length === 0) return <p className="text-sm text-ink-muted">Nothing to report.</p>;
  return (
    <ul className="space-y-2.5">
      {items.map((c) => (
        <li key={c} className="flex gap-2.5 text-sm text-ink-muted">
          <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
          <span className="min-w-0">{c}</span>
        </li>
      ))}
    </ul>
  );
}

function NarrativeSection({
  id, title, icon, items, dot,
}: { id: string; title: string; icon: LucideIcon; items: string[]; dot: string }) {
  return (
    <div id={id} className="scroll-mt-6">
      <DetailSectionCard title={title} icon={icon}>
        <BulletList items={items} dot={dot} />
      </DetailSectionCard>
    </div>
  );
}

/**
 * Full report detail — the heavy view behind a report subsection card. Carries
 * every figure and narrative section plus the export / share actions (which live
 * only on the detail page). Mock-only: actions are placeholders.
 */
export function ReportDetailPage({ report, backHref }: { report: ReportDetail; backHref: string }) {
  const title = getReportTitle(report.slug);

  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Reports"
      eyebrow={`${report.cadence} · ${report.audience}`}
      title={title}
      status={<StatusBadge tone="info" dot={false}><Sparkles className="mr-1 h-3 w-3" /> Auto-generated</StatusBadge>}
      actions={<ActionMenu items={ACTIONS} label="Export & share" />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Key figures" icon={BarChart3}>
              <FieldGrid cols={2}>
                {report.metrics.map((m) => (
                  <Field key={m.label} label={m.label} value={<span className="font-mono tnum">{m.value}</span>} />
                ))}
              </FieldGrid>
            </DetailSectionCard>

            <NarrativeSection id="changed" title="What changed" icon={TrendingUp} items={report.changed} dot="bg-success" />
            <NarrativeSection id="risks" title="Risks & blockers" icon={AlertTriangle} items={report.risks} dot="bg-warning" />
            <NarrativeSection id="next" title="Next actions" icon={ArrowRight} items={report.next} dot="bg-rose" />
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="About" icon={Info}>
              <div className="space-y-4">
                <Field label="Cadence" value={report.cadence} />
                <Field label="Audience" value={report.audience} />
                <Field label="Summary" value={report.summary} />
              </div>
            </DetailSectionCard>
            <DetailSectionCard title="Distribution" icon={Share2}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Generated automatically from live operational data. Export and share are staged
                in this environment — no report is sent externally.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
