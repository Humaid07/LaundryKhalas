import Link from "next/link";
import { FileX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getReport } from "@/lib/dashboard/reports-data";
import { ReportDetailPage } from "@/components/dashboard/reports/report-detail/ReportDetailPage";

/**
 * Full report detail route. Nested under /reports/view/ so it does not collide
 * with the static /reports/<slug> subsection routes (those stay the light
 * summaries). reportId is the report slug; back returns to the subsection.
 */
export default async function ReportDetailRoute({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId: raw } = await params;
  const reportId = decodeURIComponent(raw);
  const report = getReport(reportId);
  const backHref = `/reports/${reportId}`;

  if (!report) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <FileX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Report not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No report matches “{reportId}”.</p>
        </div>
        <Link href="/reports"><Button variant="primary" size="sm">Back to Reports</Button></Link>
      </div>
    );
  }

  return <ReportDetailPage report={report} backHref={backHref} />;
}
