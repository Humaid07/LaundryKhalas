import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getMarketingApproval } from "@/lib/dashboard/marketing-data";
import { ApprovalDetailPage } from "@/components/dashboard/marketing/approval-detail/ApprovalDetailPage";

/**
 * Dedicated full-page Marketing approval detail — where the approve / request-
 * changes / reject actions live (approval-gated, mock). The approvals list only
 * shows a light preview and links here.
 */
export default async function ApprovalDetailRoute({
  params,
}: {
  params: Promise<{ approvalId: string }>;
}) {
  const { approvalId: raw } = await params;
  const approvalId = decodeURIComponent(raw);
  const backHref = "/marketing/approvals";

  const approval = getMarketingApproval(approvalId);

  if (!approval) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <CheckCircle2 className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Approval not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No approval matches “{approvalId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Approvals</Button></Link>
      </div>
    );
  }

  return <ApprovalDetailPage approval={approval} backHref={backHref} />;
}
