import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getJob } from "@/lib/dashboard/dev-automation-data";
import { JobDetailPage } from "@/components/dashboard/dev-automation/job-detail/JobDetailPage";

/**
 * Dedicated full-page background-job detail — the primary Dev & Automation record.
 * Server component: reads the job id (name) + originating status tab from the
 * route so "back" returns to the exact job-queue view the operator came from.
 */
export default async function JobDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ jobId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { jobId: raw } = await params;
  const sp = await searchParams;
  const jobId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/dev-automation/job-queue?tab=${tab}` : "/dev-automation/job-queue";

  const job = getJob(jobId);

  if (!job) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Job not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No background job matches “{jobId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Job queue</Button></Link>
      </div>
    );
  }

  return <JobDetailPage job={job} backHref={backHref} />;
}
