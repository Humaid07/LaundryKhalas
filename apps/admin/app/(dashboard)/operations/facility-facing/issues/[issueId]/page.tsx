import { FacilityIssueDetailPage } from "@/components/dashboard/operations/facility-issue-detail/FacilityIssueDetailPage";

/**
 * Dedicated full-page detail + thread for a FACILITY-RAISED issue (Operations →
 * Facility Facing → Issues). Server component: it only decodes the id + the
 * originating tab and computes "back", so the operator returns to the exact
 * Facility Facing view they came from. The issue itself is fetched client-side
 * (the bearer token lives in the browser), so loading / not-found / error are
 * handled inside FacilityIssueDetailPage.
 */
export default async function FacilityIssueDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ issueId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { issueId: raw } = await params;
  const sp = await searchParams;
  const issueId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : "issues";
  const backHref = `/operations/facility-facing?tab=${tab}`;

  return <FacilityIssueDetailPage issueId={issueId} backHref={backHref} />;
}
